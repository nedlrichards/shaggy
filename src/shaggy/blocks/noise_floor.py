import time

import numpy as np
import zmq

from shaggy.blocks.block import Block
from shaggy.subs import noise_floor
from shaggy.proto import stft_pb2
from shaggy.transport import library

class NoiseFloor:

    def __init__(self, cfg, short_time_fft_id: str, thread_id: str, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.thread_id = thread_id
        self.context = context
        self.short_time_fft_id = short_time_fft_id
        self.sub_addresses = {
            library.BlockName.ShortTimeFFT.value: f"inproc://{short_time_fft_id}"
        }
        self.noise_floor = noise_floor.NoiseFloor.from_cfg(cfg)

        self.block = Block(
                thread_id,
                self.sub_addresses,
                library.get_block_socket(library.BlockName.NoiseFloor.value, thread_id),
                self.context
                )
        self.block.parse_sub = self.parse_sub
        self.block.parse_control = self.parse_control
        self.frame_number = 0

    def run(self):
        self.block.run()

    def parse_sub(self, sub_id, topic, timestamp_ns, message):
        stft_in = stft_pb2.STFT()
        stft_in.ParseFromString(message)

        result = self.noise_floor(message)
        if result is None:
            return

        noise_floor_dB = result
        noise_floor_dB = noise_floor_dB.detach().cpu().numpy().astype(np.float32)
        noise_floor_complex = noise_floor_dB.astype(np.complex64)
        stft_samples = noise_floor_complex[None, :, None]

        stft_msg = stft_pb2.STFT()
        stft_msg.frame_number = self.frame_number
        stft_msg.num_times_0 = 1
        stft_msg.num_fft = stft_in.num_fft
        stft_msg.sample_rate = stft_in.sample_rate
        stft_msg.num_channel_2 = 1
        stft_msg.thread_id = self.thread_id
        stft_msg.stft_samples = stft_samples.tobytes()

        msg = stft_msg.SerializeToString()
        self.block.pub_socket.send_string(library.BlockName.NoiseFloor.value, zmq.SNDMORE)
        self.block.pub_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.block.pub_socket.send_multipart([msg])
        self.frame_number += 1

    def parse_control(self, timestamp_ns, message):
        self.block.shutdown()
