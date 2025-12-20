"""Composition of buffer handling and short time FFT computation."""
from contextlib import contextmanager
import threading
import time
from typing_extensions import Annotated, Literal, Self, Optional

import numpy as np
import torch
from omegaconf import DictConfig
import zmq

from shaggy.caps.stft_buffer import STFTBuffer
from shaggy.proto import stft_pb2
from shaggy.proto import command_pb2
from shaggy.signal.functional.short_time_fft import ShortTimeFFT as STFT_Function
from shaggy import helpers

class ShortTimeFFT:
    """Composition of buffer handling and short time FFT computation."""
    def __init__(
        self, 
        window_length: int,
        stride_length: int,
        sample_rate: int,
        window_spec: str,
        adress_type: str,
        mfft: Optional[int] = None,
        scaling_spec: str = "magnitude",
        device: str = "cpu",
    ) -> Self:
        """Setup components of streaming STFT computation."""
        self.window_length = window_length
        self.stride_length = stride_length
        self.sample_rate = sample_rate
        self.window_spec = window_spec
        self.mfft = mfft
        self.scaling_spec = scaling_spec
        self.device = device

        self.sub_address = "inproc://acoustic-samples"
        self.pub_address = "inproc://stft"

        self.address_type = address_type
        self.address = helpers.get_address(address_type)

        self.frame_number = 0

        self.short_time_fft = STFT_Function.from_cfg(
            window_length=window_length,
            stride_length=stride_length,
            sample_rate=sample_rate,
            window_spec=window_spec,
            mfft=mfft,
            scaling_spec=scaling_spec,
            )
        self.short_time_fft.to(self.device)
        self.short_time_fft_buffer = STFTBuffer.from_cfg(
            window_length=window_length,
            stride_length=stride_length,
            )
        self.sub_socket = None
        self.frame_number = 0

    @classmethod
    def from_cfg(cls, cfg: DictConfig):
        """Initilize from omegaconf."""
        return cls(
            window_length=cfg['stft']['window_length'],
            stride_length=cfg['stft']['stride_length'],
            sample_rate=cfg['stft']['sample_rate'],
            window_spec=cfg['stft']['window_spec'],
            scaling_spec=cfg['stft']['scaling_spec'],
            address=cfg['global']['address_type'],
            )

    @contextmanager
    def start_stft(self, thread_id: bytes, context: zmq.Context = None):
        """Begin short time fft streaming."""
        context = context or zmq.Context.instance()

        sub = context.socket(zmq.SUB)
        sub.setsockopt_string(zmq.SUBSCRIBE, b"")
        sub.connect(self.sub_address)

        pub = context.socket(zmq.PUB)
        pub.connect(self.pub_address)

        command_socket = context.socket(zmq.SUB)
        command_socket.connect(f"inproc://command")
        command_socket.setsockopt(zmq.SUBSCRIBE, thread_id)

        poller = zmq.Poller()
        poller.register(sub, zmq.POLLIN)
        poller.register(command_socket, zmq.POLLIN)

        self.frame_number = 0

        while True:
            socks = dict(poller.poll())
            if socks.get(sub) == zmq.POLLIN:
                topic, ts_bytes, proto = sub.recv_multipart()
                samples = self.short_time_fft_buffer(proto)
                if samples is not None:
                    stft_samples = self.short_time_fft(samples)
                    self._publish_stft(stft_samples)
            if socks.get(command_socket) == zmq.POLLIN:
                ts_bytes, proto = sub.recv_multipart()
                command_msg = command_pb2.Command()
                command_msg.ParseFromString(proto)
                print(command_msg)
        sub.close(0)


    def _publish_stft(self, stft_samples):
        """Prepare STFT samples for ZMQ publish."""

        num_channels, num_freq, num_times = stft_samples.shape

        msg = stft_pb2.STFT()

        msg.frame_number = self.frame_number
        msg.num_times_0 = num_times
        msg.num_fft = self.short_time_fft.mfft
        msg.sample_rate = self.short_time_fft.sample_rate
        msg.num_channel_2 = num_channels

        sample_buf = stft_samples.numpy()
        sample_buf = np.moveaxis(sample_buf, [0, 1, 2], [-1, -2, -3])
        sample_buf = sample_buf.tobytes()
        msg.stft_samples = sample_buf
        msg = msg.SerializeToString()

        self.pub.send_string(self.pub_topic, zmq.SNDMORE)
        timestamp_ns = int(time.time() * 1e9)
        timestamp_bytes = timestamp_ns.to_bytes(8, "little")
        self.pub.send(timestamp_bytes, zmq.SNDMORE)
        self.pub.send_multipart([msg])

        self.frame_number += 1
