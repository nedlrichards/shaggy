import time

from PySide6.QtCore import QObject, Signal, Slot
import zmq

from shaggy.blocks import heartbeat
from shaggy.proto.command_pb2 import Command
from shaggy.transport import library


class Worker(QObject):
    """Proxy shared between host bridge and qt widgets."""

    command_msg = Signal(bytes, bytes, bytes)
    content_msg = Signal(bytes, bytes, bytes)

    def __init__(
        self,
        block_name: str,
        thread_id: str,
    ):
        super().__init__()
        self.block_name = block_name
        self.thread_id = thread_id
