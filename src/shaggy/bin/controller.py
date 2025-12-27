#!/usr/bin/env -S uv run

from functools import partial
import hydra
from omegaconf import DictConfig, OmegaConf
import time

from shaggy.proto.command_pb2 import Command
from shaggy import helpers

import zmq

SUBSCRIPTIONS = [
    b'heartbeat'
    ]

class Controller:
    def __init__(self, address):
        self.context = zmq.Context.instance()
        self.address = address

        self.command_socket = self.context.socket(zmq.PAIR)
        self.command_socket.bind(helpers.get_command_connection(self.address))

        self.bridge_socket = self.context.socket(zmq.SUB)
        self.bridge_socket.bind(helpers.get_bridge_connection(self.address))
        for subscription in SUBSCRIPTIONS:
            self.bridge_socket.setsockopt(zmq.SUBSCRIBE, subscription)

    def start_gstreamer_src(self, cfg, thread_id):
        msg = Command()
        msg.command = "start"
        msg.ack = False
        msg.block_name = 'gstreamer_src'
        msg.thread_id = thread_id
        msg.config = cfg
        msg = msg.SerializeToString()
        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send_string(msg)

    def shutdown_thread(self, thread_id=None):
        self.command_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.command_socket.send_string("")


def my_app() -> None:
    controller = Controller(helpers.LOCAL_HOST)

    poller = zmq.Poller()
    poller.register(controller.command_socket, zmq.POLLIN)
    poller.register(controller.bridge_socket, zmq.POLLIN)

    start_time = time.time()

    while True:
        socks = dict(poller.poll())
        if socks.get(controller.command_socket) == zmq.POLLIN:
            timestamp, message = command_socket.recv_multipart()
        if socks.get(controller.bridge_socket) == zmq.POLLIN:
            message = controller.bridge_socket.recv_multipart()
            print(message)
        if time.time() - start_time > 2.:
            controller.shutdown_thread()
            break


if __name__ == '__main__':
    my_app()
