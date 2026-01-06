from threading import Event
import time
from omegaconf import OmegaConf, Container

import zmq

from shaggy.transport import library
from shaggy.proto.command_pb2 import Command
from shaggy.workers.worker import Worker

class HostBridge():
    """ZMQ bridge that runs on the host side and manages the command socket."""

    def __init__(self, address, context: zmq.Context = None):
        self.address = address
        self.context = context or zmq.Context.instance()
        self.control_socket = self.context.socket(zmq.PAIR)
        self.control_socket.connect("inproc://host-control")
        self.command_socket = self.context.socket(zmq.PAIR)
        self.frontend = self.context.socket(zmq.SUB)
        self.workers = {}
        self.is_running = False

    def send_command(self, command: Command) -> None:
        payload = command.SerializeToString()
        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send(payload)

    def add_worker(self, message: bytes, command: Command):
        worker = Worker(command.block_name, command.thread_id)
        thread_name = library.get_thread_name(command.block_name, command.thread_id)
        self.workers[thread_name] = worker

        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send(message)

    def remove_worker(self, command: Command):
        del self.workers[library.get_thread_name(block_name, thread_id)]

    def run(self):
        self.command_socket.connect(library.get_command_connection(self.address))
        self.frontend.connect(library.get_bridge_connection(self.address))
        for topic in library.TRANSPORT_TOPICS:
            self.frontend.setsockopt_string(zmq.SUBSCRIBE, topic)
        self._poller = zmq.Poller()
        self._poller.register(self.frontend, zmq.POLLIN)
        self._poller.register(self.command_socket, zmq.POLLIN)
        self._poller.register(self.control_socket, zmq.POLLIN)
        self.is_running = True

        while self.is_running:
            socks = dict(self._poller.poll())
            if socks.get(self.frontend) == zmq.POLLIN:
                topic, timestamp, message = self.frontend.recv_multipart()
                command = Command()
                command.ParseFromString(message)
                thread_name = library.get_thread_name(command.block_name, command.thread_id)
                print(thread_name)
                self.workers[thread_name].content_msg.emit(topic, timestamp, message)
            elif socks.get(self.control_socket) == zmq.POLLIN:
                _timestamp, message = self.control_socket.recv_multipart()
                command = Command()
                command.ParseFromString(message)
                if command.command == 'startup':
                    self.add_worker(message, command)
                elif command.command == 'shutdown':
                    self.remove_worker(command)
            elif socks.get(self.command_socket) == zmq.POLLIN:
                print('hello heartbeat')
