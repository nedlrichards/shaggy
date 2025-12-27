import threading
import time

import zmq

from shaggy.blocks.block import Block
from shaggy.proto.command_pb2 import Command
from shaggy.transport import library

BLOCK_NAME = "heartbeat"

class Heartbeat:

    def __init__(self, thread_id: str, context: zmq.Context = None):
        self.thread_id = thread_id
        self.context = context or zmq.Context.instance()

        self.run_loop = True

        self.pub_socket = None
        self.control_socket = None

    def setup_sockets(self):
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(library.get_block_socket(BLOCK_NAME, self.thread_id))

        self.control_socket = self.context.socket(zmq.PAIR)
        self.control_socket.connect(library.get_control_socket(self.thread_id))

    def run(self):
        self.setup_sockets()
        thread_name = library.get_thread_name(BLOCK_NAME, self.thread_id)

        poller = zmq.Poller()
        poller.register(self.control_socket, zmq.POLLIN)
        self.run_loop = True

        while self.run_loop:
            socks = dict(poller.poll(1000))
            if socks.get(self.control_socket) == zmq.POLLIN:
                break
            self.pub_socket.send_string(BLOCK_NAME, zmq.SNDMORE)
            timestamp_ns = time.monotonic_ns()
            self.pub_socket.send_string(f"{timestamp_ns}", zmq.SNDMORE)
            self.pub_socket.send_string(thread_name)

    def parse_control(self, message):
        self.shutdown()
