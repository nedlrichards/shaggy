"""Composition of buffer handling and short time FFT computation."""
from contextlib import contextmanager
import threading
import time
from typing_extensions import Annotated, Literal, Self, Optional

import numpy as np
import torch
from omegaconf import DictConfig
import zmq

from shaggy.subs.stft_buffer import STFTBuffer
from shaggy.proto import stft_pb2
from shaggy.blocks.block import Block
from shaggy.blocks import gstreamer_src
from shaggy.signal.short_time_fft import ShortTimeFFT as STFT_Function
from shaggy.transport import library

class ShortTimeFFT:
    """Composition of buffer handling and short time FFT computation."""
    def __init__(self, cfg, gstreamer_src_id: str, thread_id: str, context: zmq.Context = None):
        """Setup components of streaming STFT computation."""
        self.context = context or zmq.Context.instance()
        self.thread_id = thread_id

        self.short_time_fft = STFT_Function.from_cfg(cfg)
        self.short_time_fft_buffer = STFTBuffer.from_cfg(cfg)

        self.gstreamer_src_id = gstreamer_src_id
        self.sub_addresses = {
            library.BlockName.GStreamerSrc.value: f"inproc://{gstreamer_src_id}"
        }
        self.block = Block(
                thread_id,
                self.sub_addresses,
                library.get_block_socket(library.BlockName.ShortTimeFFT.value, thread_id),
                self.context
                )
        self.block.parse_sub = self.parse_sub
        self.block.parse_control = self.parse_control
        self.frame_number = 0

    def run(self):
        self.frame_number = 0
        self.block.run()

    def parse_sub(self, sub_id, topic, timestamp_ns, message):
        samples = self.short_time_fft_buffer(message)
        if samples is None:
            return
        stft_samples = self.short_time_fft(samples)
        for sample in list(stft_samples):
            self._publish_stft(sample[None, ...])

    def parse_control(self, timestamp_ns, message):
        self.block.shutdown()

    def _publish_stft(self, stft_samples):
        """Prepare STFT samples for ZMQ publish."""

        num_channels, num_freq, num_times = stft_samples.shape

        msg = stft_pb2.STFT()

        msg.frame_number = self.frame_number
        msg.num_times_0 = num_times
        msg.num_fft = self.short_time_fft.mfft
        msg.sample_rate = self.short_time_fft.sample_rate
        msg.num_channel_2 = num_channels
        msg.thread_id = self.thread_id

        sample_buf = stft_samples.numpy()
        sample_buf = np.moveaxis(sample_buf, [0, 1, 2], [-1, -2, -3])
        sample_buf = sample_buf.tobytes()
        msg.stft_samples = sample_buf
        msg = msg.SerializeToString()


        self.block.pub_socket.send_string(library.BlockName.ShortTimeFFT.value, zmq.SNDMORE)
        self.block.pub_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        self.block.pub_socket.send_multipart([msg])

        self.frame_number += 1
