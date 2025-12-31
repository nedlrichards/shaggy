import time

from PySide6.QtCore import QObject, Slot
import zmq

from shaggy.transport import library
from shaggy.proto.command_pb2 import Command

class HostBridge(QObject):
    """ZMQ bridge that runs on the host side and manages the command socket."""

    def __init__(self, address, context: zmq.Context = None):
        super().__init__()
        self.address = address
        self.context = context or zmq.Context.instance()
        self.command_socket = self.context.socket(zmq.PAIR)
        self.command_socket.connect(library.get_command_connection(self.address))

    @Slot(object)
    def send_command(self, command: Command) -> None:
        payload = command.SerializeToString()
        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send(payload)
