from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import QThread

from shaggy.workers.heartbeat import HeartbeatWorker

class HeartbeatStatus(QWidget):

    def __init__(self, address, host_bridge):
        super().__init__()

        self.heartbeat_indicator = QLabel("Heartbeat")
        self.heartbeat_indicator.setStyleSheet("""background-color: #FF0000; """)
        self.heartbeat_indicator.setMargin(4)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self.heartbeat_indicator)

        self.heartbeat_worker = HeartbeatWorker(address, host_bridge)
        self.heartbeat_thread = QThread()
        self.heartbeat_worker.moveToThread(self.heartbeat_thread)
        self.heartbeat_worker.status.connect(self.set_heartbeat_status)
        self.heartbeat_thread.started.connect(self.heartbeat_worker.start)
        self.heartbeat_thread.start()

    def set_heartbeat_status(self, heartbeat_status):
        if heartbeat_status:
            self.heartbeat_indicator.setStyleSheet("""background-color: #00FF00; """)
        else:
            self.heartbeat_indicator.setStyleSheet("""background-color: #FF0000; """)
