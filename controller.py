#!/usr/bin/env -S uv run

from contextlib import contextmanager, ExitStack
from functools import partial
import hydra
from omegaconf import DictConfig, OmegaConf
import time

from shaggy.proto.command_pb2 import Command
from shaggy import helpers

import zmq

@contextmanager
def open_control(address):

    context = zmq.Context()
    control_socket = context.socket(zmq.PAIR)
    control_socket.bind(f"tcp://{address}:8800")

    try:
        yield control_socket
    finally:
        control_socket.close()
        context.term()


def publish_command(control_socket, command, config):
    """Prepare STFT samples for ZMQ publish."""
    msg = Command()
    msg.ack = False
    msg.command = command
    msg.config = OmegaConf.to_yaml(config)
    msg = msg.SerializeToString()

    timestamp_ns = int(time.time() * 1e9)
    timestamp_bytes = timestamp_ns.to_bytes(8, "little")
    control_socket.send(timestamp_bytes, zmq.SNDMORE)
    control_socket.send_multipart([msg])

@hydra.main(version_base=None, config_path="conf", config_name="collect")
def my_app(cfg: DictConfig) -> None:
    address = helpers.get_address(cfg)
    with ExitStack() as stack:
        control_socket = stack.enter_context(open_control(address))
        send = partial(publish_command, control_socket)
        send("start-audio", cfg)
        time.sleep(2.)


if __name__ == '__main__':
    my_app()
