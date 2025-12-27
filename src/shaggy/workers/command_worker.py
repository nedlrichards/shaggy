import time

from PySide6.QtCore import QObject, Slot
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library


class CommandWorker(QObject):
    """Bridge Qt slot calls into camera daemon command messages."""

    def __init__(self, address: str = None, context: zmq.Context = None):
        super().__init__()
        self.context = context or zmq.Context.instance()
        self.address = address or library.LOCAL_HOST
        self._socket = None

    def _ensure_socket(self):
        if self._socket is None:
            self._socket = self.context.socket(zmq.PAIR)
            self._socket.connect(library.get_command_connection(self.address))

    @Slot(str, str)
    def shutdown(self, block_name: str, thread_id: str):
        """Send a shutdown command for a specific block/thread."""
        self._ensure_socket()
        msg = Command()
        msg.command = "shutdown"
        msg.ack = False
        msg.block_name = block_name
        msg.thread_id = thread_id
        payload = msg.SerializeToString()
        timestamp = f"{time.monotonic_ns()}"
        self._socket.send_string(block_name, zmq.SNDMORE)
        self._socket.send_string(timestamp, zmq.SNDMORE)
        self._socket.send(payload)

    @Slot()
    def close(self):
        if self._socket is not None:
            self._socket.close(0)
            self._socket = None
