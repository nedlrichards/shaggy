import time

import zmq

from shaggy.blocks.block import Block
from shaggy.blocks import gstreamer_src
from shaggy.subs import channel_levels
from shaggy.proto.samples_pb2 import Samples
from shaggy.proto import channel_levels_pb2
from shaggy.transport import library

BLOCK_NAME = "channel-levels"

class ChannelLevels:

    def __init__(self, cfg, gstreamer_src_id: str, thread_id: str, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.thread_id = thread_id
        self.context = context
        self.gstreamer_src_id = gstreamer_src_id
        self.sub_addresses = {
                gstreamer_src.BLOCK_NAME: f"inproc://{gstreamer_src_id}"
                }
        self.channel_levels = channel_levels.ChannelLevels.from_cfg(cfg)

        self.block = Block(
                thread_id,
                self.sub_addresses,
                library.get_block_socket(BLOCK_NAME, thread_id),
                self.context
                )
        self.block.parse_sub = self.parse_sub
        self.block.parse_control = self.parse_control
        self.frame_number = 0

    def run(self):
        self.block.run()

    def parse_sub(self, sub_id, topic, timestamp_ns, message):
        samples = Samples()
        levels_dB = self.channel_levels(message)
        if levels_dB is None:
            return
        samples.ParseFromString(message)
        channel_levels = channel_levels_pb2.ChannelLevels()
        channel_levels.frame_number = self.frame_number
        channel_levels.num_channels_0 = samples.num_channels_1
        channel_levels.levels = levels_dB.numpy().tobytes()
        msg = channel_levels.SerializeToString()

        self.block.pub_socket.send_string(BLOCK_NAME, zmq.SNDMORE)
        self.block.pub_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.block.pub_socket.send_multipart([msg])

        self.frame_number += 1

    def parse_control(self, timestamp_ns, message):
        self.block.shutdown()
