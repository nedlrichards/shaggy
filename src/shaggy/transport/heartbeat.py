import time

from PySide6.QtCore import QObject, Signal, Slot
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.transport.host_bridge import HostBridge
from shaggy.transport.q_proxy import QProxy


class HeartbeatWorker(QObject):
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
        self.q_proxy = QProxy(
            library.BlockName.Heartbeat.value,
            self.thread_id,
            self.host_bridge,
        )
