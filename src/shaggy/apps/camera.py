#!/usr/bin/env -S uv run

import threading
import time

import click
from omegaconf import OmegaConf
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft
from shaggy.workers.edge_bridge import EdgeBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator

@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    address = library.get_address(address_type)
    edge_bridge = EdgeBridge(address)
    thread_id_generator = ThreadIDGenerator()
    command_socket = edge_bridge.context.socket(zmq.PAIR)
    command_socket.bind(library.get_command_connection(address))

    stft_cfg = {
            'window_length': 12000,
            'stride_length': 6000,
            'window_spec': "HAMMING",
            'scaling_spec': "psd", 
            }
    cfg = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}

    edge_bridge_thread = threading.Thread(target=edge_bridge.run)
    edge_bridge_thread.start()

    command = Command()
    command.command = 'startup'
    command.thread_id = thread_id_generator()
    command.block_name = heartbeat.BLOCK_NAME
    command.config = OmegaConf.to_yaml(OmegaConf.create(cfg))

    command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
    command_socket.send(command.SerializeToString())

    command.thread_id = thread_id_generator()
    command.block_name = gstreamer_src.BLOCK_NAME

    command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
    command_socket.send(command.SerializeToString())

    command.thread_id = thread_id_generator()
    command.block_name = channel_levels.BLOCK_NAME

    command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
    command_socket.send(command.SerializeToString())

    command.thread_id = thread_id_generator()
    command.block_name = short_time_fft.BLOCK_NAME

    command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
    command_socket.send(command.SerializeToString())


if __name__ == "__main__":
    my_app()
