import time

from PySide6.QtCore import QObject, Signal, Slot
import zmq

from shaggy.blocks import heartbeat
from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.transport.host_bridge import HostBridge


class QProxy(QObject):
    """Proxy shared between host bridge and qt widgets."""

    control_msg = Signal(bytes, bytes, bytes)
    content_msg = Signal(bytes, bytes, bytes)

    def __init__(
        self,
        block_name: str,
        thread_id: str,
        host_bridge: HostBridge,
    ):
        super().__init__()
        self.block_name = block_name
        self.thread_id = thread_id
        self.host_bridge = host_bridge

    def startup(self) -> None:
        pass

    @Slot()
    def send_command(self, msg) -> None:
        pass

    @Slot()
    def shutdown(self) -> None:
        pass
