#!/usr/bin/env -S uv run

import signal
import sys
import threading
import time

from contextlib import contextmanager, ExitStack

import click
import hydra
from omegaconf import DictConfig, OmegaConf
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft
from shaggy.workers.command_handler import CommandHandler
from shaggy.workers.edge_bridge import EdgeBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator

@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    address = library.get_address(address_type)
    command_handler = command_handler.CommandHandler(address)
    edge_bridge = edge_bridge.EdgeBridge(address)
    thread_id_generator = ThreadIDGenerator()

    stft_cfg = {
            'window_length': 12000,
            'stride_length': 6000,
            'window_spec': "HAMMING",
            'scaling_spec': "psd", 
            }
    cfg = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}

    command = Command()
    command.command = 'startup'
    command.thread_id = thread_id_generator()
    command.block_name = heartbeat.BLOCK_NAME
    command.config = OmegaConf.to_yaml(OmegaConf.create(cfg))

    heartbeat_id = edge_bridge.startup(command)

    command.thread_id = thread_id_generator()
    command.block_name = gstreamer_src.BLOCK_NAME

    gstreamer_src_id = edge_bridge.startup(command)

    command.thread_id = thread_id_generator()
    command.block_name = channel_levels.BLOCK_NAME

    channel_levels_id = edge_bridge.startup(command)

    command.thread_id = thread_id_generator()
    command.block_name = short_time_fft.BLOCK_NAME

    short_time_fft_id = edge_bridge.startup(command)

    edge_bridge.run()

if __name__ == "__main__":
    my_app()
