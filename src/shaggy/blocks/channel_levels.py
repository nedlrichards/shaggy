from shaggy.blocks.block import Block
from shaggy.blocks import gstreamer_src
from shaggy.subs import channel_levels
from shaggy.proto.samples_pb2 import Samples
from shaggy.proto.channel_levels_pb2 import ChannelLevels
from shaggy.transport import library

import zmq

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

    def parse_sub(self, sub_id, sub_socket):
        topic, timestamp_ns, message = sub_socket.recv_multipart()
        samples = Samples()
        samples.ParseFromString(samples)
        levels_dB = self.channel_levels(samples.samples)
        channel_levels = ChannelLevels()
        channel_levels.frame_number = self.frame_number
        channel_levels.num_channels_0 = Samples.num_channels_1
        channel_levels.levels = levels_dB.tobytes()
        msg = channel_levels.SerializeToString()

        self.block.pub_socket.send_string(BLOCK_NAME, zmq.SNDMORE)
        timestamp_ns = int(time.time() * 1e9)
        timestamp_bytes = timestamp_ns.to_bytes(8, "little")
        self.block.pub_socket.send(timestamp_bytes, zmq.SNDMORE)
        self.block.pub_socket.send_multipart([msg])

        self.frame_number += 1


    def parse_control(self, message):
        self.block.shutdown()
