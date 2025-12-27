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
from shaggy.blocks.heartbeat import Heartbeat
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator

class Camera:

    def __init__(self, address):
        self.context = zmq.Context.instance()
        self.address = address
        self.command_socket = self.context.socket(zmq.PAIR)
        self.command_socket.connect(library.get_command_connection(self.address))

        self.frontend = self.context.socket(zmq.SUB)
        self.frontend.bind(library.FRONTEND_ADDRESS)

        self.backend = self.context.socket(zmq.PUB)
        self.backend.connect(library.get_bridge_connection(self.address))

        self.command_pairs = {}
        self.block_threads = {}

    def start_block(self, thread_target, block_name, thread_id):
        thread_name = library.get_thread_name(block_name, thread_id)

        command = self.context.socket(zmq.PAIR)
        command.bind(library.get_control_socket(thread_id))
        self.command_pairs[thread_name] = command

        heartbeat_thread = threading.Thread(target=thread_target)
        heartbeat_thread.start()

        self.block_threads[thread_name] = heartbeat_thread

        block_socket = library.get_block_socket(block_name, thread_id)
        self.frontend.connect(block_socket)
        self.frontend.setsockopt_string(zmq.SUBSCRIBE, block_name)
        return thread_name

    def start_heartbeat(self, thread_id):
        instance = heartbeat.Heartbeat(thread_id, self.context)
        thread_name = self.start_block(instance.run, heartbeat.BLOCK_NAME, thread_id)
        return thread_name

    def start_gstreamer_src(self, cfg, thread_id):
        instance = gstreamer_src.GStreamerSrc.from_cfg(cfg, thread_id, self.context)
        thread_name = self.start_block(instance.run, gstreamer_src.BLOCK_NAME, thread_id)
        return thread_name

    def start_channel_levels(self, cfg, gstreamer_src_id, thread_id):
        instance = channel_levels.ChannelLevels(cfg, gstreamer_src_id, thread_id, self.context)
        self.start_block(instance.run, channel_levels.BLOCK_NAME, thread_id)
        return thread_id

    def start_short_time_fft(self, cfg, gstreamer_src_id, thread_id):
        instance = short_time_fft.ShortTimeFFT(cfg, gstreamer_src_id, thread_id, self.context)
        self.start_block(instance.run, channel_levels.BLOCK_NAME, thread_id)
        return thread_id

    def shutdown(self, thread_id=None):
        if thread_id is not None:
            command_pairs = {thread_id: self.command_pairs[thread_id]}
            block_threads = {thread_id: self.block_threads[thread_id]}
        else:
            command_pairs = self.command_pairs
            block_threads = self.block_threads

        for id, pair_socket in command_pairs.items():
            pair_socket.send_string("shutdown", zmq.SNDMORE)
            pair_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
            pair_socket.send_string("")

        for _, block_thread in block_threads.items():
            block_thread.join()
        sys.exit(0)

    def termintate(self, sig, frame):
        self.shutdown()

@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    address = library.get_address(address_type)
    command_handler = Camera(address)
    thread_id_generator = ThreadIDGenerator()

    heartbeat_id = command_handler.start_heartbeat(thread_id_generator())
    stft_cfg = {
            'window_length': 12000,
            'stride_length': 6000,
            'window_spec': "HAMMING",
            'scaling_spec': "psd", 
            }
    cfg = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}
    gstreamer_src_id = command_handler.start_gstreamer_src(cfg, thread_id_generator())
    channel_levels_id = command_handler.start_channel_levels(cfg, gstreamer_src_id, thread_id_generator())
    short_time_fft_id = command_handler.start_short_time_fft(cfg, gstreamer_src_id, thread_id_generator())

    poller = zmq.Poller()
    poller.register(command_handler.command_socket, zmq.POLLIN)
    poller.register(command_handler.frontend, zmq.POLLIN)
    signal.signal(signal.SIGINT, command_handler.termintate)

    while True:
        socks = dict(poller.poll())
        if socks.get(command_handler.command_socket) == zmq.POLLIN:
            topic, timestamp, message = command_handler.command_socket.recv_multipart()
            command_handler.shutdown()
            break
        if socks.get(command_handler.frontend) == zmq.POLLIN:
            topic, timestamp, msg = command_handler.frontend.recv_multipart()
            command_handler.backend.send_multipart((topic, timestamp, msg))

if __name__ == "__main__":
    my_app()
