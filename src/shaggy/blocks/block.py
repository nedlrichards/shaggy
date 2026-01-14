import threading
import zmq

from shaggy.transport import library

class Block:

    def __init__(self, thread_id: str, sub_addresses: dict, pub_address: str, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.thread_id = thread_id

        self.sub_addresses = sub_addresses
        self.pub_address = pub_address

        self._running = threading.Event()

        self.sub_sockets = None
        self.pub_socket = None
        self.control_socket = None

    def run(self):
        poller = self._setup_sockets()
        self.startup_hook(poller)

        self._running.set()
        while self._running.is_set():
            socks = dict(poller.poll())
            for sub_id, sub_socket in self.sub_sockets.items():
                if socks.get(sub_socket) == zmq.POLLIN:
                    topic, timestamp_ns, message = sub_socket.recv_multipart()
                    self.parse_sub(sub_id, topic, int(timestamp_ns), message)
            if socks.get(self.control_socket) == zmq.POLLIN:
                timestamp_ns, message = self.control_socket.recv_multipart()
                self.parse_control(int(timestamp_ns), message) 

        for _, sub_socket in self.sub_sockets.items():
            sub_socket.close(0)
        self.pub_socket.close(0)
        self.control_socket.close(0)
        self.shutdown_hook()

    def _setup_sockets(self):
        self.sub_sockets = {}
        for id, address in self.sub_addresses.items():
            socket = self.context.socket(zmq.SUB)
            socket.connect(address)
            socket.setsockopt_string(zmq.SUBSCRIBE, id)
            self.sub_sockets[id] = socket

        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(self.pub_address)

        self.control_socket = self.context.socket(zmq.PAIR)
        self.control_socket.bind(library.get_control_socket(self.thread_id))

        poller = zmq.Poller()
        for sub_id, sub_socket in self.sub_sockets.items():
            poller.register(sub_socket, zmq.POLLIN)
        poller.register(self.control_socket, zmq.POLLIN)
        return poller

    def parse_sub(self, sub_id, topic, timestamp_ns, message):
        pass

    def parse_control(self, timestamp_ns, message):
        pass

    def startup_hook(self, poller: zmq.Poller):
        pass

    def shutdown_hook(self):
        pass

    def shutdown(self):
        self._running.clear()
