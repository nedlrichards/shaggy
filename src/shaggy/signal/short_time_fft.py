"""
Short time FFT matches scipy.signal.ShortTimeFFT stride and padding conventions.

Can be run in batch or buffered processing.
"""

import torch
from pydantic import Field
from pydantic.dataclasses import dataclass
from torch import Tensor
from typing_extensions import Annotated, Literal, Self, Optional

from shaggy.signal import windows


@dataclass
class ShortTimeFFTConfig:
    """Definition of a short time fft.

    Attributes:
        window_length: Integer number of data samples used in each FFT.
        stride_length: Integer number of data samples between each FFT, less than or equal to window_length.
        sample_rate: Integer number of data samples per second.
        window_spec: A window string specifier used by acoustic.signal.windows.
        mfft: Integer number of samples in each FFT, greater than or equal to window_length.
        scaling_spec: "magnitude" scales result as a spectrum of sinusoidal magnitude,
            "density" scales to a power spectral density.
    """

    window_length: Annotated[int, Field(gt=0)]
    stride_length: Annotated[int, Field(gt=0)]
    sample_rate: Annotated[int, Field(gt=0)]
    window_spec: str = "HAMMING"
    mfft: Optional[int] = None
    scaling_spec: Annotated[str, Literal["magnitude", "psd"]] = "magnitude"

    def __post_init__(self) -> Self:
        """Parameter checks and default values."""
        if self.stride_length > self.window_length:
            raise ValueError("Stride length much be less than or equal to window length")
        if self.mfft is None:
            self.mfft = self.window_length
        elif self.mfft < self.window_length:
            raise ValueError(
                "FFT length much be greater than or equal to window length"
            )


class ShortTimeFFT(torch.nn.Module):
    """A reduced functionality torch port of scipy ShortTimeFFT."""

    def __init__(self, config: ShortTimeFFTConfig) -> Self:
        """
        Setup short time FFT.

        Attributes:
            window_length: Integer number of data samples used in each FFT.
            stride_length: Integer number of data samples between each FFT, less than or equal to window_length.
            sample_rate: Integer number of data samples per second.
            window_spec: A window string specifier used by acoustic.signal.windows.
            mfft: Integer number of samples in each FFT, greater than or equal to window_length.
            scaling_spec: "magnitude" scales result as a spectrum of sinusoidal magnitude,
                "density" scales to a power spectral density.
        """
        super().__init__()
        window = windows.discretized(config.window_length, config.window_spec)
        self.register_buffer("window", window)
        self.window_length = config.window_length
        self.stride_length = config.stride_length
        self.mfft = config.mfft
        self.sample_rate = config.sample_rate
        self.f_axis = (
            torch.arange(config.mfft // 2 + 1, dtype=torch.float32) * config.sample_rate / config.mfft
        )
        self.window_spec = config.window_spec
        self.m_num_mid = config.window_length // 2
        self.scaling_spec = config.scaling_spec
        self.first_index, _ = self._pre_padding()

        if config.scaling_spec == "psd":
            scaling = torch.sqrt(2 / (self.sample_rate * (self.window**2).sum()))
        elif config.scaling_spec == "magnitude":
            scaling = torch.sqrt(2 / (self.window.sum() ** 2))
        else:
            raise ValueError("Scaling type must be psd or magnitude.")
        self.register_buffer("scaling", scaling)

        self.unprocessed_samples = None

    @classmethod
    def from_cfg(cls, cfg) -> Self:
        """Initilize class instance from keywords."""
        stft_cfg = ShortTimeFFTConfig(
                window_length=cfg['stft']['window_length'],
                stride_length=cfg['stft']['stride_length'],
                sample_rate=cfg['gstreamer_src']['sample_rate'],
                window_spec=cfg['stft']['window_spec'],
                mfft=cfg['stft'].get('mfft'),
                scaling_spec=cfg['stft']['scaling_spec'],
                )
        return cls(stft_cfg)

    def forward(self, timeseries: Tensor) -> Tensor:
        """Bulk data implimentation of a short time FFT.

        Args:
            timeseries: Data with shape (*, num_samples).
        """
        num_samples = timeseries.shape[-1]
        if num_samples < self.window_length:
            raise ValueError(
                f"Number of samples ({num_samples}) must be greater than window_length ({self.window_length})"
            )
        x = timeseries.unfold(-1, self.window_length, self.stride_length)

        if x.shape[-1] < self.mfft:  # zero pad if needed
            z_shape = list(x.shape)
            z_shape[-1] = self.mfft - x.shape[-1]
            x = torch.hstack((x, torch.zeros(z_shape, dtype=x.dtype, device=x.device)))

        x = x * self.window
        x = torch.fft.rfft(x, dim=-1)
        x = torch.movedim(x, 2, 1)

        return x * self.scaling

    def get_time_axis(self, processed_stft: Tensor) -> Tensor:
        """Time axis of stft."""
        num_times = processed_stft.shape[1]
        index_number = torch.arange(num_times, dtype=torch.float32)
        index_number *= self.stride_length
        index_number + self.first_index
        return index_number / self.sample_rate

    def pad_timeseries(self, timeseries: Tensor) -> Tensor:
        """Add pre and post padding for timeseries reconstruction."""
        padded_timeseries = self.post_pad_timeseries(timeseries)
        padded_timeseries = self.pre_pad_timeseries(padded_timeseries)
        return padded_timeseries

    def pre_pad_timeseries(self, timeseries: Tensor) -> Tensor:
        """Add pre padding for timeseries reconstruction."""
        pre_pad_shape = list(timeseries.shape)[:-1] + [abs(self.first_index)]
        padded_timeseries = torch.cat([torch.zeros(pre_pad_shape), timeseries], dim=-1)
        return padded_timeseries

    def post_pad_timeseries(self, timeseries: Tensor) -> Tensor:
        """Add post padding for timeseries reconstruction."""
        num_samples = timeseries.shape[-1]
        last_index, _ = self._post_padding(num_samples)
        post_pad_shape = list(timeseries.shape)[:-1] + [last_index - num_samples]
        padded_timeseries = torch.cat([timeseries, torch.zeros(post_pad_shape)], dim=-1)
        return padded_timeseries

    def finalize_buffer(self, stft_result: Tensor) -> Tensor:
        """Compute final samples in FFT after data stream has closed.

        Args:
            stft_result: Current short time FFT result.
        """
        num_windows = stft_result.shape[1]
        num_padded_samples = self.window_length + (num_windows - 1) * self.stride_length
        num_samples = num_padded_samples - abs(self.first_index)
        num_samples += self.unprocessed_samples.shape[-1]
        num_samples -= abs(self.first_index)
        num_post_padding, _ = self._post_padding(num_samples)
        padding_shape = [stft_result.shape[2]] + [num_post_padding - num_samples]
        padding = torch.zeros(
            padding_shape, dtype=stft_result.dtype.to_real(), device=stft_result.device
        )
        padded_timeseries = torch.cat([self.unprocessed_samples, padding], dim=1)
        return self(padded_timeseries)

    def _pre_padding(self) -> tuple[int, int]:
        """Smallest signal index and slice index due to padding.

        Since, per convention, for time t=0, n,q is zero, the returned values
        are negative or zero.
        """
        w2 = self.window**2
        # move window to the left until the overlap with t >= 0 vanishes:
        n0 = -self.m_num_mid
        for q_, n_ in enumerate(
            range(n0, n0 - self.window_length - 1, -self.stride_length)
        ):
            n_next = n_ - self.stride_length
            if n_next + self.window_length <= 0 or all(w2[n_next:] == 0):
                return n_, -q_
        raise RuntimeError("This is code line should not have been reached!")

    def _post_padding(self, n: int) -> tuple[int, int]:
        """Largest signal index and slice index due to padding.

        Parameters
        ----------
        n : int
            Number of samples of input signal (must be ≥ half of the window length).
        """
        if not (n >= (m2p := self.window_length - self.m_num_mid)):
            raise ValueError(f"Parameter n must be >= ceil(window_length/2) = {m2p}!")
        w2 = self.window**2
        # move window to the right until the overlap for t < t[n] vanishes:
        q1 = n // self.stride_length  # last slice index with t[p1] <= t[n]
        k1 = q1 * self.stride_length - self.m_num_mid
        for q_, k_ in enumerate(
            range(k1, n + self.window_length, self.stride_length), start=q1
        ):
            n_next = k_ + self.stride_length
            if n_next >= n or all(w2[: n - n_next] == 0):
                return k_ + self.window_length, q_ + 1
        raise RuntimeError("This is code line should not have been reached!")
