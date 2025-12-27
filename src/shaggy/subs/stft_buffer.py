"""Converts streaming audio data to tensor following kernel and stride length.
"""

from typing_extensions import Annotated, Literal, Self

from pydantic.dataclasses import dataclass
from pydantic import Field
import numpy as np
import torch

from shaggy.proto.samples_pb2 import Samples

@dataclass
class STFTBufferConfig:
    """Definition of kernel transform."""
    window_length: Annotated[int, Field(gt=0)]
    stride_length: Annotated[int, Field(gt=0)]
    device: Literal["cpu", "cuda"] = "cpu"

    def __post_init__(self) -> Self:
        """Parameter checks and default values."""
        if self.stride_length > self.window_length:
            raise ValueError("Stride length much be less than or equal to window length.")

class STFTBuffer():
    """Transform streaming data to kernel strided data."""

    def __init__(self, config: STFTBufferConfig) -> Self:
        """Setup kernel transform."""
        self.window_length = config.window_length
        self.stride_length = config.stride_length
        self.device = config.device
        self.buffer = b""
        self.sample_width = 4
        self.dtype = np.float32

    @classmethod
    def from_cfg(cls, cfg) -> Self:
        """Initilize class instance from keywords."""
        stft_kernel_config = STFTBufferConfig(
                window_length=cfg['stft']['window_length'],
                stride_length=cfg['stft']['stride_length'],
                )
        return cls(stft_kernel_config)

    def __call__(self, samples_proto: bytes) -> torch.Tensor:
        """Stride data to create kernels.
        Args:
            sample_proto: Sample protobuf string.

        Returns:
            kernels: (num_kernels, ..., window_length).
        """
        msg = Samples()
        msg.ParseFromString(samples_proto)

        num_channels = msg.num_channels_1
        sample_buffer = msg.samples
        sample_stride = num_channels * self.sample_width
        self.buffer += sample_buffer
        num_samples = len(self.buffer) // sample_stride

        if num_samples < self.window_length:
            return


        num_buffers = 1 + (num_samples - self.window_length) // self.stride_length
        num_excess = (num_samples - self.window_length) % self.stride_length
        num_short = self.stride_length - num_excess

        num_samples = self.window_length + (num_buffers - 1) * self.stride_length
        num_remainder = self.window_length - num_short
        samples = self.buffer[: num_samples * sample_stride]
        self.buffer = self.buffer[-num_remainder * sample_stride :]


        samples = np.frombuffer(samples, dtype=self.dtype)
        samples = samples.reshape((num_channels, -1))
        samples = samples.copy()
        samples = torch.from_numpy(samples).to(device=self.device)

        return samples
