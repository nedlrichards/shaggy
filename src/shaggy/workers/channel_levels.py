from PySide6.QtCore import QObject, Signal, Slot
import zmq

from shaggy.transport import library
from shaggy.blocks import channel_levels


class ChannelLevelWorker(QObject):
    """Listen for channel levels PUB messages and emit payloads."""

    message_received = Signal(bytes)

    def __init__(self, address: str, context: zmq.Context = None):
        super().__init__()
        self.address = address
        self.context = context or zmq.Context.instance()
        self._running = False

        self.bridge_socket = self.context.socket(zmq.SUB)
        self.bridge_socket.connect(library.get_bridge_connection(self.address))
        self.bridge_socket.setsockopt_string(zmq.SUBSCRIBE, channel_levels.BLOCK_NAME)

    @Slot()
    def start(self) -> None:
        poller = zmq.Poller()
        poller.register(self.bridge_socket, zmq.POLLIN)

        self._running = True
        while self._running:
            socks = dict(poller.poll())
            if socks.get(self.bridge_socket) == zmq.POLLIN:
                _topic, _timestamp, message = self.bridge_socket.recv_multipart()
                self.message_received.emit(message)

    @Slot()
    def shutdown(self) -> None:
        self._running = False
