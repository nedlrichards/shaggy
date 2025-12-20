
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst, GstVideo  # noqa E402
Gst.init(None)

from PySide6.QtCore import QMetaObject, Qt

from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Signal, Slot
import sys
import os
import time

CAMERA_IMAGE_WIDTH = 3840
CAMERA_IMAGE_HEIGHT = 2160
CAMERA_FRAME_RATE = 15
class VideoStream(QWidget):
    set_handle_signal = Signal()

    def __init__(self):
        super().__init__()
        self.video = QWidget()
        self.video.setAttribute(Qt.WA_NativeWindow)
        self.video.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.set_handle_signal.connect(self.set_window_id)
        self.pipeline = None
        self.sink = None
        self.textoverlay = None
        self.recordpipe = None
        self.appsrc = None
        self.setup_gstreamer()

    def setup_gstreamer(self):
        """Start GStreamer."""

        pipeline = (
            f" v4l2src device=/dev/video2 do-timestamp=true name=srcc"
            f" ! video/x-raw, format=YUY2, width={CAMERA_IMAGE_WIDTH},"
            f"height={CAMERA_IMAGE_HEIGHT},framerate={CAMERA_FRAME_RATE}/1"
            " ! videoconvert"
            " ! tee name=tee"
            " ! queue max-size-bytes=0 max-size-time=0 max-size-buffers=10 leaky=downstream"
            " ! videoconvert "
            " ! compositor name=compositor"
            " ! textoverlay color=0xfffecb00 valignment=top halignment=left"
            " line-alignment=left font-desc='Sans, 72' name=textoverlay"
            " ! videoconvert"
            " ! glimagesink name=sink"
        )

        print(f"Using pipeline: {pipeline}")
        self.pipeline = Gst.parse_launch(pipeline)
        if self.pipeline is None:
            raise ValueError('gstreamer pipeline has not initilized.')

        bus = self.pipeline.get_bus()
        bus.enable_sync_message_emission()
        bus.connect("sync-message::element", self.on_sync_message)

        self.textoverlay = self.pipeline.get_by_name("textoverlay")
        self.pipeline.set_state(Gst.State.PLAYING)

    def on_sync_message(self, bus, msg):
        if msg.get_structure() is None:
            return
        message_name = msg.get_structure().get_name()
        if msg.get_structure().get_name() == "prepare-window-handle":
            QMetaObject.invokeMethod(self, "set_window_id", Qt.QueuedConnection)

    def set_window_id(self):
        sink = self.pipeline.get_by_name("sink")
        sink.set_window_handle(self.winId())

    def on_record_click(self):
        """Start up recording."""
        if self.recordpipe:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.video_size = 0

        data_dir = os.path.expanduser('~/data/temp')

        self.curent_save_dir = os.path.join(data_dir, "temp")
        os.makedirs(self.curent_save_dir, exist_ok=True)
        self.video_file = f"{self.curent_save_dir}/recording.mkv"

        self.recordpipe = Gst.parse_bin_from_description(
            "queue ! videoconvert ! openh264enc ! h264parse"
            f" ! matroskamux ! filesink location={self.video_file}"
            " sync=false name=filesink",
            True,
        )

        src_pad = self.recordpipe.get_by_name("filesink").get_static_pad("sink")
        assert src_pad
        src_pad.add_probe(
            Gst.PadProbeType.BUFFER, self.gstreamer_filesink_probe_callback
        )

        self.pipeline.set_state(Gst.State.PAUSED)
        self.pipeline.add(self.recordpipe)
        self.pipeline.get_by_name("tee").link(self.recordpipe)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.record_start = time.time()

    def stop_recording(self):
        """Stop recording."""
        self.recordpipe.set_state(Gst.State.PAUSED)
        self.pipeline.get_by_name("tee").unlink(self.recordpipe)
        self.pipeline.remove(self.recordpipe)
        self.recordpipe.set_state(Gst.State.NULL)
        self.recordpipe = None

        os.system(
            f"mkvmerge -o {self.video_file}.fixed {self.video_file}"
            f" && mv {self.video_file}.fixed {self.video_file}"
        )


    def gstreamer_filesink_probe_callback(self, pad, info):
        """Get the buffer from the probe info."""
        buffer = info.get_buffer()
        if buffer:
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                try:
                    data = map_info.data
                    self.video_size += len(data)
                finally:
                    buffer.unmap(map_info)
        return Gst.PadProbeReturn.OK


    def closeEvent(self, event):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        event.accept()

