import time

from PySide6.QtCore import QObject, Signal, Slot
import zmq

from shaggy.transport import library


class GStreamerWorker(QObject):
    message_received = Signal(bytes)

    def __init__(self, address: str):
        super().__init__()
        self.sub_socket = library.get_bridge_connection(address)
        self._running = False

    def start(self):
        """Runs inside the QThread."""
        socket = context.socket(zmq.SUB)
        socket.connect(self.endpoint)
        socket.setsockopt(zmq.SUBSCRIBE, b"gstreamer-src")

        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)

        self._running = True
        while self._running:
            events = dict(poller.poll())
            if socket in events:
                msg = socket.recv()
                self.message_received.emit(msg)
        socket.close(0)

    @Slot()
    def shutdown(self):
        # TODO: send shutdown command.
        self._running = False
