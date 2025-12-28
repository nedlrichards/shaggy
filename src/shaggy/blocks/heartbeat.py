import threading
import time

import zmq

from shaggy.blocks.block import Block
from shaggy.proto.command_pb2 import Command
from shaggy.subs import heartbeat_src
from shaggy.transport import library

BLOCK_NAME = 'heartbeat'
HEARTBEAT_MAX_MISSES = 3

class Heartbeat:
    def __init__(self, thread_id: str, context: zmq.Context = None):
        self.thread_id = thread_id
        self.context = context or zmq.Context.instance()

        self.heartbeat_src = heartbeat_src.HeartbeatSrc(thread_id, self.context)
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_src.run)

        self.sub_addresses = {
            BLOCK_NAME: library.get_block_socket(BLOCK_NAME, thread_id)
        }
        self.block = Block(
            thread_id,
            self.sub_addresses,
            library.get_block_socket(BLOCK_NAME, thread_id),
            self.context,
        )
        self.block.parse_sub = self.parse_sub
        self.block.parse_control = self.parse_control
        self.block.shutdown = self.shutdown

        self.num_misses = 0

        self._running = False
        self._last_ack_time = time.monotonic()

    def startup(self, poller):
        self.heartbeat_thread.start()

    def shutdown(self):
        self.heartbeat_src.shutdown()
        self.heartbeat_thread.join()

    def parse_sub(self, sub_id, topic, timestamp_ns, message):
        self.num_misses += 1
        if self.num_misses > HEARTBEAT_MAX_MISSES:
            print("hello")

    def parse_control(self, timestamp_ns, message):
        command = Command()
        command.ParseFromString(message)
        if command.command == "shutdown":
            self._running = False
        if command.command == BLOCK_NAME:
            self.num_misses = 0
