import sys
import time

import zmq

from shaggy.transport import library
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft
from shaggy.workers.command_handler import CommandHandler

TRANSPORT_TOPICS = [
        heartbeat.BLOCK_NAME,
        ]

class EdgeBridge:
    """ZMQ bridge that runs on the device side and manages block threads."""

    def __init__(self, address, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.command_socket = self.context.socket(zmq.PAIR)
        self.frontend = self.context.socket(zmq.SUB)
        self.backend = self.context.socket(zmq.PUB)
        self._running = False
        self.command_handler = CommandHandler(address, self.context)

    def run(self):

        self.command_socket.connect(library.get_command_connection(self.address))
        self.frontend.bind(library.FRONTEND_ADDRESS)
        self.backend.connect(library.get_bridge_connection(self.address))

        poller = zmq.Poller()
        poller.register(command_handler.command_socket, zmq.POLLIN)
        poller.register(command_handler.frontend, zmq.POLLIN)

        self._running = True

        while self._running:
            socks = dict(poller.poll())
            if socks.get(self.command_socket) == zmq.POLLIN:
                timestamp, message = self.command_socket.recv_multipart()
                command = Command()
                command.ParseFromString(message)
                if command.command == 'startup':
                    self.startup(command)
                else:
                    self.shutdown()
                break
            if socks.get(self.frontend) == zmq.POLLIN:
                topic, timestamp, msg = self.frontend.recv_multipart()
                if topic in TRANSPORT_TOPICS:
                    self.backend.send_multipart((topic, timestamp, msg))

    def startup(self, command):
        block_socket = library.get_block_socket(command.block_name, command.thread_id)

        if command.block_name == heartbeat.BLOCK_NAME:
            thread_id = self.command_handler.start_heartbeat(command.thread_id)
        elif command.block_name == gstreamer_src.BLOCK_NAME:
            thread_id = self.command_handler.start_gstreamer_src(command.config, command.thread_id)
        elif command.block_name == channel_levels.BLOCK_NAME:
            thread_id = self.command_handler.start_channel_levels(self.gstreamer_src_id, command.config, command.thread_id)
        elif command.block_name == short_time_fft.BLOCK_NAME:
            thread_id = self.command_handler.start_short_time_fft(self.gstreamer_src_id, command.config, command.thread_id)
        self.frontend.connect(block_socket)
        self.frontend.setsockopt_string(zmq.SUBSCRIBE, command.block_name)

        return thread_id

    def shutdown(self, thread_name = None):
        if thread_name is not None:
            # TODO: allow for the shutdown of specific threads
            print('not supported')
        self._running = False


