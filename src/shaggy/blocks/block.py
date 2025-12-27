import zmq

from shaggy.transport import library

class Block:

    def __init__(self, thread_id: str, sub_addresses: dict, pub_address: str, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.thread_id = thread_id

        self.sub_addresses = sub_addresses
        self.pub_address = pub_address

        self._running = False

        self.sub_sockets = None
        self.pub_socket = None
        self.control_socket = None

    def setup_sockets(self):
        self.sub_sockets = {}
        for id, address in self.sub_addresses.items():
            socket = self.context.socket(zmq.SUB)
            socket.connect(address)
            socket.setsockopt_string(zmq.SUBSCRIBE, id)
            self.sub_sockets[id] = socket

        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.connect(self.pub_address)

        self.control_socket = self.context.socket(zmq.PAIR)
        self.control_socket.connect(library.get_control_socket(self.thread_id))

    def run(self):
        self.setup_sockets()
        poller = zmq.Poller()
        for sub_id, sub_socket in self.sub_sockets.items():
            poller.register(sub_socket, zmq.POLLIN)
        poller.register(self.control_socket, zmq.POLLIN)

        self._running = True
        while self._running:
            socks = dict(poller.poll())
            for sub_id, sub_socket in self.sub_sockets.items():
                if socks.get(sub_socket) == zmq.POLLIN:
                    self.parse_sub(sub_id, sub_socket)
            if socks.get(self.control_socket) == zmq.POLLIN:
                message = self.control_socket.recv()
                self.parse_control(message) 

        for _, sub_socket in self.sub_sockets.items():
            sub_socket.close()
        self.pub_socket.close()
        self.control_socket.close()

    def parse_sub(self, sub_id, sub_socket):
        pass

    def parse_control(self, message):
        pass

    def shutdown(self):
        self._running = False
