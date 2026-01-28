"""Beamform with a fixed angle hypothesis."""

import torch
from acoustic.mic_array.mic_array import Array
from acoustic.signal import angle_schema
from acoustic.signal.functional import beamform
from torch import Tensor
from typing_extensions import Self


class Beamformer:
    """Common beamformer class."""

    def __init__(
        self,
        mic_array: Array,
        sample_rate: int,
        window_length: int,
        angle_schema: angle_schema.AngleSchema,
        speed_of_sound: float,
        f_bounds: list[float],
    ) -> Self:
        """Initialize Beamformer."""
        self.mic_array = mic_array
        self.sample_rate = sample_rate
        self.window_length = window_length
        self.angle_schema = angle_schema
        self.angles = angle_schema.angles
        self.speed_of_sound = speed_of_sound
        f_axis = (
            torch.arange(self.window_length // 2 + 1, dtype=torch.float32)
            / self.window_length
        )
        self.f_bounds = f_bounds
        f_axis = f_axis * self.sample_rate
        self.full_f_axis = f_axis.detach().clone()
        self.f_idx = torch.searchsorted(self.full_f_axis, torch.tensor(self.f_bounds))
        self.f_axis = f_axis[self.f_idx[0] : self.f_idx[1]]
        self.wave_numbers = beamform.wave_numbers(
            self.angles, self.f_axis, self.speed_of_sound
        )
        steering_vectors = beamform.steering_vectors(
            self.wave_numbers, self.mic_array.sensor_positions
        )
        self.register_buffer("steering_vectors", steering_vectors)


class BartlettBeamformer(torch.nn.Module, Beamformer):
    """A Bartlett, a.k.a delay and sum, beamformer."""

    def __init__(
        self,
        mic_array: Array,
        sample_rate: int,
        window_length: int,
        angle_schema: angle_schema.AngleSchema,
        speed_of_sound: float,
        f_bounds,
    ) -> Self:
        """Initialize Bartlett beamformer."""
        torch.nn.Module.__init__(self)
        Beamformer.__init__(
            self,
            mic_array=mic_array,
            sample_rate=sample_rate,
            window_length=window_length,
            angle_schema=angle_schema,
            speed_of_sound=speed_of_sound,
            f_bounds=f_bounds,
        )

    def trim_samples(self, samples):
        """Trim STFT samples to match beamformer frequency bounds."""
        samples = samples[self.f_idx[0] : self.f_idx[1]]
        return samples

    def forward(self, samples, freq_idx=None, trim_samples=True):
        """Beamform to angle hypothesis."""
        samples = self.trim_samples(samples) if trim_samples else samples
        if freq_idx is not None:
            samples = samples[freq_idx]
            steering_vectors = self.steering_vectors[:, freq_idx]
        else:
            steering_vectors = self.steering_vectors

        return beamform.bartlett_beamform(samples, steering_vectors)


class MVDRBeamformer(torch.nn.Module, Beamformer):
    """Minimum variance distortionless receiver (MVDR) beamformer."""

    def __init__(
        self,
        mic_array,
        diagonal_loading: float,
        num_snapshots: int,
        step: int,
        sample_rate: int,
        window_length: int,
        angle_schema: angle_schema.AngleSchema,
        speed_of_sound: float,
        f_bounds,
    ) -> Self:
        """Initialize the minimum variance distortionless receiver (MVDR) beamformer."""
        torch.nn.Module.__init__(self)
        Beamformer.__init__(
            self,
            mic_array=mic_array,
            sample_rate=sample_rate,
            window_length=window_length,
            angle_schema=angle_schema,
            speed_of_sound=speed_of_sound,
            f_bounds=f_bounds,
        )
        self.diagonal_loading = diagonal_loading
        self.num_snapshots = num_snapshots
        self.step = step

    def forward(self, samples):
        """Beamform to angle hypothesis."""
        samples = samples[:, self.f_idx[0] : self.f_idx[1]]
        covariance = beamform.covariance(samples, self.num_snapshots, self.step)
        mvdr_filter_vectors = beamform.mvdr_filter_vectors(
            covariance, self.steering_vectors, self.diagonal_loading
        )
        destination_idx = torch.arange(samples.shape[0], device=samples.device)
        selection_idx = torch.ceil(
            (destination_idx - (self.num_snapshots - 1)) / self.step
        )
        selection_idx = selection_idx.clamp(0, mvdr_filter_vectors.shape[2] - 1).to(
            torch.int64
        )
        associated_filter_vectors = mvdr_filter_vectors.index_select(1, selection_idx)
        return beamform.bartlett_beamform(samples, associated_filter_vectors)

    def buffered_forward(self, samples: Tensor) -> Tensor:
        """Beamform to angle hypothesis from buffer input."""
        1 / 0  # TODO: implement
        return self(samples)
