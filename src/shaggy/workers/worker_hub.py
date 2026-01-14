from typing import Optional
import time

from PySide6.QtCore import QObject, QThread, Slot
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.workers.worker import Worker

class WorkerHub(QObject):

    def __init__(self, address: str, context: zmq.Context = None):
        super().__init__()
        self.address = address
        self.context = context or zmq.Context.instance()

        self.command_socket = None
        self.workers = {}
        self.worker_threads = {}

    @Slot()
    def start(self) -> None:
        if self.command_socket is None:
            self.command_socket = self.context.socket(zmq.PAIR)
            self.command_socket.connect(library.get_command_connection(self.address))

    @Slot(Command)
    def send_command(self, command: Command) -> None:
        payload = command.SerializeToString()
        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send(payload)

    @Slot(Command)
    def add_worker(self, command: Command):
        worker = Worker(
            command.block_name,
            command.thread_id,
            command.block_name,
            self.address,
        )
        worker_thread = QThread()
        worker.moveToThread(worker_thread)
        worker_thread.started.connect(worker.run)
        thread_name = library.get_thread_name(command.block_name, command.thread_id)
        self.workers[thread_name] = worker
        self.worker_threads[thread_name] = worker_thread
        worker_thread.start()

        if command.block_name != library.BlockName.Heartbeat.value:
            payload = command.SerializeToString()
            self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
            self.command_socket.send(payload)

    def get_worker(self, block_name: str, thread_id: Optional[str]) -> Worker | None:
        thread_name = library.get_thread_name(block_name, thread_id)
        return self.workers[thread_name]

    @Slot(Command)
    def remove_worker(self, command: Command):
        payload = command.SerializeToString()
        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send(payload)

        thread_name = library.get_thread_name(command.block_name, command.thread_id)
        worker = self.workers[thread_name]
        worker.shutdown()
        worker_thread = self.worker_threads[thread_name]
        worker_thread.quit()
        worker_thread.wait()
        del self.worker_threads[thread_name]
        del self.workers[thread_name]

    @Slot(bytes, bytes, bytes)
    def handle_transport_message(
        self,
        topic: bytes,
        timestamp: bytes,
        message: bytes,
    ) -> None:
        topic_name = topic.decode()
        message_type = library.TRANSPORT_TOPICS[topic_name]

        content = message_type()
        content.ParseFromString(message)
        thread_name = library.get_thread_name(topic_name, content.thread_id)
        worker = self.workers[thread_name]
        worker.content_msg.emit(topic, timestamp, message)
