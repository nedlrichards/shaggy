"""Accumulate Short time FFT results into a covariance estimate."""
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

class Covariance(torch.nn.Module):
    def __init__(self, num_windows: int, window_hop: int):
        super().__init__()
        self.num_windows = num_windows
        self.window_hop = window_hop
        self.frame_number = 0
        self.stft_samples = []

    def forward(self, stft_samples: torch.Tensor):
        stft_samples = list(stft_samples)
        self.stft_samples += stft_samples

        covariance_result = []
        while len(self.stft_samples) >= self.num_windows:
            if self.frame_number == 0:
                covariance = self._compute_covariance(self.stft_samples[:self.num_windows])
                covariance_result.append(covariance)
            self.stft_samples = self.stft_samples[1:]
            self.frame_number = (self.frame_number + 1) % self.window_hop

        if len(covariance_result) == 0:
            return
        elif len(covariance_result) == 1:
            return covariance_result[0]
        else:
            raise ValueError('If you want to do this, implement it.')

    def _compute_covariance(self, stft_samples):
        samples = torch.stack(stft_samples, dim=0)
        covariance = torch.einsum("ijk,ijl->jkl", samples, samples.conj())
        return covariance
