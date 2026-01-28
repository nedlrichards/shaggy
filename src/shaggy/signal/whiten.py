"""Whiten power spectrum density."""

import torch
from acoustic.signal import power_spectral_density
from torch import Tensor
from typing_extensions import Optional


class Whiten(torch.nn.Module):
    """Remove model fit from power spectrum."""

    def __init__(self, f_bounds, num_sections, window_length, sample_rate):
        """Setup."""
        super().__init__()
        self.f_bounds = f_bounds
        self.num_sections = num_sections
        self.window_length = window_length
        self.sample_rate = sample_rate
        f_axis = (
            torch.arange(self.window_length // 2 + 1)
            / self.window_length
            * self.sample_rate
        )
        self.register_buffer("f_axis", f_axis)
        f_idx = torch.searchsorted(
            self.f_axis,
            torch.tensor([self.f_bounds[0], self.f_bounds[1]]),
        )
        self.register_buffer("f_idx", f_idx)
        self.power_spectral_density = power_spectral_density.PowerSpectralDensity()
        self.register_buffer("noise_fit", torch.empty(0))

    def get_trimmed_f_axis(self) -> Tensor:
        """Get frequency axis of whitened audio."""
        return self.f_axis[self.f_idx[0] : self.f_idx[1]]

    def forward(self, short_time_fft: Tensor) -> Tensor:
        """Whiten spectra."""
        if self.noise_fit.shape[0] == 0:
            raise ValueError("Noise floor not defined.")
        whitened_stft = (
            short_time_fft[self.f_idx[0] : self.f_idx[1]]
            / self.noise_fit[:, None, None]
        )
        return whitened_stft

    def fit_noise(self, short_time_fft: Tensor) -> Optional[Tensor]:
        """Add short time fft to power estimate."""
        psd = self.power_spectral_density(short_time_fft)
        f_axis = self.f_axis[self.f_idx[0] : self.f_idx[1]]
        psd = psd[self.f_idx[0] : self.f_idx[1]]
        log_f = torch.log10(f_axis)
        n_bins = 40
        edges = torch.logspace(log_f[0], log_f[-1], n_bins + 1)

        idx = torch.bucketize(f_axis, edges) - 1
        valid = (idx >= 0) & (idx < len(edges) - 1)
        psd_ds = torch.stack(
            [psd[idx[valid] == i].median() for i in range(len(edges) - 1)]
        )
        psd_dB = 10 * torch.log10(psd_ds)
        predictor = torch.ones([psd_dB.shape[0], 2])
        predictor[:, 1] = torch.log10(edges[1:])
        p = torch.linalg.lstsq(predictor, psd_dB).solution
        noise_fit_dB = p[0] + log_f * p[1]
        self.noise_fit = 10 ** (noise_fit_dB / 20)
        return noise_fit_dB
