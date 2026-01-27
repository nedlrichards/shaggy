import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst, GstVideo

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout

Gst.init(None)


class CameraDisplay(QWidget):
    def __init__(self, port: int = 51234) -> None:
        super().__init__()
        self.port = port
        self._pipeline = None

        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        src_caps = "application/x-rtp, media=video, encoding-name=H264, payload=96"
        pipeline_str = (
            f'udpsrc port={self.port} caps="{src_caps}"'
            " ! rtph264depay ! avdec_h264 ! videoconvert"
            " ! xvimagesink name=video_sink sync=false"
        )
        self._pipeline = Gst.parse_launch(pipeline_str)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._pipeline:
            return
        sink = self._pipeline.get_by_name("video_sink")
        if sink and hasattr(GstVideo, "VideoOverlay"):
            GstVideo.VideoOverlay.set_window_handle(sink, int(self.winId()))
        self._pipeline.set_state(Gst.State.PLAYING)

    def closeEvent(self, event) -> None:
        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
        super().closeEvent(event)
