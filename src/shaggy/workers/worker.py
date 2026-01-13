from PySide6.QtCore import QObject, Signal, Slot
import zmq

from omegaconf import Container

from shaggy.transport import library


class Worker(QObject):
    """Proxy shared between host bridge and qt widgets."""

    content_msg = Signal(bytes, bytes, bytes)

    def __init__(
        self,
        block_name: str,
        thread_id: str,
        transport_topic: str,
        address: str,
        context: zmq.Context = None,
    ):
        super().__init__()
        self.block_name = block_name
        self.thread_id = thread_id
        self.transport_topic = transport_topic
        self.address = address
        self.context = context or zmq.Context.instance()

        self.frontend = self.context.socket(zmq.SUB)
        thread_name = library.get_thread_name(self.block_name, self.thread_id)
        self.poller_control_address = f"inproc://poller-control-{thread_name}"
        self.poller_control_socket = self.context.socket(zmq.PAIR)
        self.poller_control_socket.bind(self.poller_control_address)

    def run(self, cfg: Container = None):
        self.frontend.connect(library.get_bridge_connection(self.address))
        self.frontend.setsockopt_string(zmq.SUBSCRIBE, self.transport_topic)
        local_control_socket = self.context.socket(zmq.PAIR)
        local_control_socket.connect(self.poller_control_address)

        self._poller = zmq.Poller()
        self._poller.register(self.frontend, zmq.POLLIN)
        self._poller.register(local_control_socket, zmq.POLLIN)

        while True:
            socks = dict(self._poller.poll())
            if socks.get(local_control_socket) == zmq.POLLIN:
                break
            if socks.get(self.frontend) == zmq.POLLIN:
                self.content_msg.emit(*self.frontend.recv_multipart())

    @Slot()
    def shutdown(self):
        self.poller_control_socket.send(b"")
