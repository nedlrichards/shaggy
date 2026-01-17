"""Power spectrum density noise floor estimate."""

import numpy as np
import torch

from shaggy.proto import stft_pb2
from shaggy.signal.covariance import Covariance
from shaggy.signal.noise_floor import NoiseFloor as NoiseFloorSignal


class NoiseFloor:
    """Estimate noise floor of power spectrum."""

    def __init__(
        self,
        num_windows: int,
        window_hop: int,
        f_min: float,
        f_max: float,
        num_sections: int = 10,
    ):
        self.covariance = Covariance(num_windows, window_hop)
        self.f_min = f_min
        self.f_max = f_max
        self.num_sections = num_sections
        self.noise_floor = None
        self._f_index = None
        self._f_axis = None

    @classmethod
    def from_cfg(cls, cfg):
        """Initilize class instance from keywords."""
        noise_cfg = cfg["noise_floor"]
        return cls(
            num_windows=noise_cfg["num_windows"],
            window_hop=noise_cfg["window_hop"],
            f_min=noise_cfg["f_min"],
            f_max=noise_cfg["f_max"],
        )

    def _build_frequency_axis(self, num_fft: int, sample_rate: int):
        f_axis = torch.arange(num_fft // 2 + 1, dtype=torch.float32)
        f_axis = f_axis * sample_rate / num_fft
        f_index = (f_axis >= self.f_min) & (f_axis <= self.f_max)
        return f_axis[f_index], f_index

    def __call__(self, msg: bytes):
        stft_msg = stft_pb2.STFT()
        stft_msg.ParseFromString(msg)
        stft_shape = (stft_msg.num_times_0, -1, stft_msg.num_channel_2)
        stft_flat = np.frombuffer(stft_msg.stft_samples, dtype=np.complex64)

        stft_samples = stft_flat.reshape(stft_shape)
        stft_samples = torch.from_numpy(stft_samples)
        if self._f_axis is None:
            self._f_axis, self._f_index = self._build_frequency_axis(
                stft_msg.num_fft,
                stft_msg.sample_rate,
            )
            self.noise_floor = NoiseFloorSignal(self._f_axis, self.num_sections)
        stft_samples = stft_samples[:, self._f_index, :]

        covariance = self.covariance(stft_samples)
        if covariance is None:
            return None
        noise_fit_dB = self.noise_floor.fit_noise(covariance)

        num_freq = stft_msg.num_fft // 2 + 1
        full_noise_fit_dB = torch.empty(
            num_freq,
            dtype=noise_fit_dB.dtype,
            device=noise_fit_dB.device,
        )
        full_noise_fit_dB[self._f_index] = noise_fit_dB
        f_indices = torch.nonzero(self._f_index, as_tuple=False).flatten()
        first_idx = int(f_indices[0].item())
        last_idx = int(f_indices[-1].item())
        if first_idx > 0:
            full_noise_fit_dB[:first_idx] = noise_fit_dB[0]
        if last_idx + 1 < num_freq:
            full_noise_fit_dB[last_idx + 1 :] = noise_fit_dB[-1]

        return full_noise_fit_dB
