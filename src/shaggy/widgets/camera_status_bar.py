from PySide6.QtWidgets import QStatusBar, QPushButton

from shaggy.widgets.heartbeat_status import HeartbeatStatus


class CameraStatusBar(QStatusBar):

    def __init__(self, host_bridge, parent=None):
        super().__init__(parent)
        self.showMessage("Ready", 5000)

        self.heartbeat_status = HeartbeatStatus(host_bridge)
        self.record_button = QPushButton("Record")
        self.record_button.setCheckable(True)
        self.record_button.setEnabled(False)

        self.addPermanentWidget(self.heartbeat_status)
        self.addPermanentWidget(self.record_button)

        self.record_button.clicked.connect(self._switch_record_text)

    def _switch_record_text(self, checked: bool):
        self.record_button.setText("Stop" if checked else "Record")
