from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Slot

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.workers.heartbeat import Heartbeat

class HeartbeatStatus(QWidget):
    def __init__(self, host_bridge):
        super().__init__()
        self.host_bridge = host_bridge

        command = Command()
        command.command = 'startup'
        command.block_name = library.BlockName.Heartbeat.value
        self.host_bridge.worker_hub.add_worker(command)

        self.heartbeat_indicator = QLabel("Heartbeat")
        self.heartbeat_indicator.setStyleSheet("""background-color: #FF0000; """)
        self.heartbeat_indicator.setMargin(4)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self.heartbeat_indicator)
        self.heartbeat = Heartbeat(self.host_bridge)
        self.heartbeat.status.connect(self.set_heartbeat_status)

    @Slot(bool)
    def set_heartbeat_status(self, heartbeat_status):
        if heartbeat_status:
            self.heartbeat_indicator.setStyleSheet("""background-color: #00FF00; """)
        else:
            self.heartbeat_indicator.setStyleSheet("""background-color: #FF0000; """)
