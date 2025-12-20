#!/usr/bin/env -S uv run

import signal
from threading import Event
import time

from contextlib import contextmanager, ExitStack

import click
import hydra
from omegaconf import DictConfig, OmegaConf
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.caps.acoustic_src import AcousticSrc
from shaggy import helpers

def get_exit_event():
    exit_event = Event()

    def quit_event(signo, _frame):
        print("Interrupted by %d, shutting down" % signo)
        exit_event.set()

    signal.signal(signal.SIGTERM, quit_event)
    signal.signal(signal.SIGINT, quit_event)
    signal.signal(signal.SIGHUP, quit_event)  
    return exit_event

class CommandHandler:

    def __init__(self):
        self.stft_runners = []
        self.detection_runners = []
        self.acoustic_src = None
        self.pipeline = None

    def startup(self, cfg, exit_stack):
        self.acoustic_src = AcousticSrc.from_cfg(cfg)
        self.pipeline = exit_stack.enter_context(self.acoustic_src.start_audio())



@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    address = helpers.get_address(address_type)

    context = zmq.Context.instance()
    command_socket = context.socket(zmq.PAIR)
    command_socket.connect(f"tcp://{address}:8800")

    local_command_socket = context.socket(zmq.PUB)
    local_command_socket.connect(f"inproc://command")

    frontend = context.socket(zmq.SUB)
    frontend.connect("inproc://stft_samples")

    backend = context.socket(zmq.PUB)
    backend.bind(f"tcp://{address}:8100")
    frontend.setsockopt(zmq.SUBSCRIBE, b'')

    poller = zmq.Poller()
    poller.register(command_socket, zmq.POLLIN)

    command_handler = CommandHandler()

    exit_event = get_exit_event()

    with ExitStack() as stack:
        while not exit_event.is_set():
            socks = dict(poller.poll(100))
            if socks.get(command_socket) == zmq.POLLIN:
                timestamp, message = command_socket.recv_multipart()
                # TODO: Handle logic, send out local commands if action needed by threads.
                #command_msg = Command()
                #command_msg.ParseFromString(message)

            if socks.get(frontend) == zmq.POLLIN:
                message = frontend.recv_multipart()
                backend.send_multipart(message)



if __name__ == "__main__":
    my_app()
