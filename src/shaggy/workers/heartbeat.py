from PySide6.QtCore import QObject, Signal, Slot, QTimer

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.transport.host_bridge import HostBridge


class Heartbeat(QObject):
    """Listen for heartbeat PUB messages, ack, and emit timeout status."""

    status = Signal(bool)

    def __init__(
        self,
        host_bridge: HostBridge,
        thread_id: str,
        timeout_s: float = 3.,
    ):
        super().__init__()
        self.host_bridge = host_bridge
        self.thread_id = thread_id
        self.timeout_s = timeout_s
        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.setInterval(int(self.timeout_s * 1000))
        self.timeout_timer.timeout.connect(self._emit_timeout)
        self.timeout_timer.start()
        self.worker = self.host_bridge.command_hub.get_worker(
            library.BlockName.Heartbeat.value,
            self.thread_id,
        )
        self.worker.content_msg.connect(self.repeat_heartbeat)

    @Slot(bytes, bytes, bytes)
    def repeat_heartbeat(self, topic, timestamp, msg):
        command = Command()
        command.ParseFromString(msg)
        command.ack = True

        self.host_bridge.command_hub.send_command(command)
        self.status.emit(True)
        self.timeout_timer.start()

    @Slot()
    def _emit_timeout(self) -> None:
        self.status.emit(False)
