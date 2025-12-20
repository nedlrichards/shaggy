import zmq

class Block:

    def __init__(self, thread_id: str, sub_addresses: dict, control_address: str, pub_address: str, context: zmq.Context = None):
        context = context or zmq.Context.instance()
        self.thread_id = thread_id

        self.sub_addresses - sub_addresses
        self.sub_sockets = {}
        for id, address in sub_addresses.items():
            socket = context.socket(zmq.SUB)
            socket.connect(address)
            socket.setsockopt_string(zmq.SUBSCRIBE, "")
            self.sub_sockets[id] = socket

        self.pub_address = pub_address
        self.pub_socket = context.socket(zmq.PUB)
        self.pub_socket.connect(pub_address)

        self.control_address = control_address
        self.control_socket = context.socket(zmq.PUB)
        self.control_socket.connect(control_address)

        self.run_loop = True

        return pub_socket, control_socket

    def run(self):
        poller = zmq.Poller()
        for _, sub_sockets in self.sub_sockets.items():
            poller.register(sub_sockets, zmq.POLLIN)
        poller.register(self.control_socket, zmq.POLLIN)

        self.run_loop = True
        while run_loop:
            socks = dict(poller.poll())
            for sub_id, sub_socket in self.sub_sockets.items():
                if socks.get(sub_socket) == zmq.POLLIN):
                    self.parse_sub(sub_id, sub_socket)
            if socks.get(control_socket) == zmq.POLLIN:
                self.parse_control() 

        self.pub_socket.close()
        self.control_socket.close()

    def parse_sub(self, sub_id, sub_socket):
        pass

    def parse_control(self):
        pass

    def shutdown(self):
        self.run_loop = False
