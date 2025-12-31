from PySide6.QtCore import QObject, Signal, Slot
import zmq

from shaggy.blocks import heartbeat
from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.workers.host_bridge import HostBridge


class HeartbeatWorker(QObject):
    """Listen for heartbeat PUB messages, ack, and emit timeout status."""

    status = Signal(bool)

    def __init__(
        self,
        address: str,
        host_bridge: HostBridge,
        context: zmq.Context = None,
        timeout_ms: int = 3000,
    ):
        super().__init__()
        self.address = address
        self.host_bridge = host_bridge
        self.context = context or zmq.Context.instance()
        self.timeout_ms = timeout_ms
        self._running = False

        self.bridge_socket = self.context.socket(zmq.SUB)
        self.bridge_socket.connect(library.get_bridge_connection(self.address))
        self.bridge_socket.setsockopt_string(zmq.SUBSCRIBE, heartbeat.BLOCK_NAME)

    @Slot()
    def start(self) -> None:
        poller = zmq.Poller()
        poller.register(self.bridge_socket, zmq.POLLIN)

        self._running = True
        while self._running:
            socks = dict(poller.poll(self.timeout_ms))
            if socks.get(self.bridge_socket) == zmq.POLLIN:
                topic, timestamp, message = self.bridge_socket.recv_multipart()
                heartbeat_command = Command()
                heartbeat_command.ParseFromString(message)
                heartbeat_command.ack = True
                self.host_bridge.send_command(heartbeat_command)
                self.status.emit(True)
            else:
                self.status.emit(False)

    def shutdown(self) -> None:
        self._running = False
