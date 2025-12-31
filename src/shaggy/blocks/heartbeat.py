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
            BLOCK_NAME: library.get_block_socket(heartbeat_src.BLOCK_NAME, thread_id)
        }
        self.block = Block(
            thread_id,
            self.sub_addresses,
            library.get_block_socket(BLOCK_NAME, thread_id),
            self.context,
        )
        self.block.parse_sub = self.parse_sub
        self.block.parse_control = self.parse_control
        self.block.startup_hook = self.startup_hook
        self.block.shutdown_hook = self.shutdown_hook

        self.num_misses = 0

    def run(self):
        self.block.run()

    def startup_hook(self, poller):
        self.heartbeat_thread.start()

    def shutdown_hook(self):
        self.heartbeat_src.shutdown()
        self.heartbeat_thread.join()

    def parse_sub(self, sub_id, topic, timestamp_ns, message):
        command = Command()
        command.command = BLOCK_NAME
        command.ack = False
        command.block_name = BLOCK_NAME
        command.thread_id = self.thread_id
        payload = command.SerializeToString()

        self.block.pub_socket.send_string(BLOCK_NAME, zmq.SNDMORE)
        self.block.pub_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.block.pub_socket.send(payload)

        self.num_misses += 1
        if self.num_misses > HEARTBEAT_MAX_MISSES:
            shutdown = Command()
            shutdown.command = "shutdown"
            shutdown.block_name = BLOCK_NAME
            shutdown.thread_id = self.thread_id
            payload = shutdown.SerializeToString()
            self.block.control_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
            self.block.control_socket.send(payload)

    def parse_control(self, timestamp_ns, message):
        command = Command()
        command.ParseFromString(message)
        if command.command == "shutdown":
            self.block.shutdown()
        if command.command == BLOCK_NAME:
            self.num_misses = 0
