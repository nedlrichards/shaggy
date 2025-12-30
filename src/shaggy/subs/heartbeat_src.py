import threading
import time

import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.blocks import heartbeat

class HeartbeatSrc:
    def __init__(self, thread_id: str, context: zmq.Context = None, interval_s: float = 1.0):
        self.thread_id = thread_id
        self.context = context or zmq.Context.instance()
        self.interval_s = interval_s
        self._running = threading.Event()
        self.pub_socket = None

    def setup_socket(self):
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(library.get_block_socket(heartbeat.BLOCK_NAME, self.thread_id))

    def run(self):
        self.setup_socket()
        self._running.set()
        while self._running.is_set():
            payload = self._compose_payload()
            self.pub_socket.send_string(heartbeat.BLOCK_NAME, zmq.SNDMORE)
            timestamp_ns = time.monotonic_ns()
            self.pub_socket.send_string(f"{timestamp_ns}", zmq.SNDMORE)
            self.pub_socket.send(payload)
            time.sleep(self.interval_s)
        self.pub_socket.close(0)

    def _compose_payload(self):
        command = Command()
        command.command = heartbeat.BLOCK_NAME
        command.ack = False
        command.block_name = heartbeat.BLOCK_NAME
        command.thread_id = self.thread_id
        payload = command.SerializeToString()
        return payload

    def shutdown(self):
        self._running.clear()
