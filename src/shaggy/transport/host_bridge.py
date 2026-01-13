import zmq

from shaggy.transport import library
from shaggy.workers.worker_hub import WorkerHub

class HostBridge:
    """ZMQ bridge that runs on the host side and manages the command socket."""

    def __init__(self, address, context: zmq.Context = None):
        self.address = address
        self.context = context or zmq.Context.instance()

        self.frontend = self.context.socket(zmq.SUB)
        self.command_hub = WorkerHub(self.address, self.context)
        self.command_hub.start()

    def run(self):
        self.frontend.connect(library.get_bridge_connection(self.address))
        for topic in library.TRANSPORT_TOPICS.keys():
            self.frontend.setsockopt_string(zmq.SUBSCRIBE, topic)
        self._poller = zmq.Poller()
        self._poller.register(self.frontend, zmq.POLLIN)
        self.is_running = True

        while True:
            socks = dict(self._poller.poll())
            if socks.get(self.frontend) == zmq.POLLIN:
                topic, timestamp, message = self.frontend.recv_multipart()
                self.command_hub.handle_transport_message(topic, timestamp, message)
