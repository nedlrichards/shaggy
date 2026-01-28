"""Power spectrum density noise floor estimate."""

import torch
from torch import Tensor


class NoiseFloor(torch.nn.Module):
    """Estimate noise floor of power spectrum."""

    def __init__(self, f_axis, num_sections=10):
        """Setup."""
        super().__init__()
        self.f_axis = f_axis
        self.num_sections = num_sections

    def fit_noise(self, covariance: Tensor):
        """Add short time fft to power estimate."""
        psd = torch.einsum('jii->ji', covariance).real
        log_f = torch.log10(self.f_axis)
        edges = torch.logspace(log_f[0], log_f[-1], self.num_sections + 1)

        idx = torch.bucketize(self.f_axis, edges) - 1
        valid = (idx >= 0) & (idx < len(edges) - 1)
        psd_ds = torch.stack(
            [psd[idx[valid] == i].median() for i in range(len(edges) - 1)]
        )
        psd_dB = 10 * torch.log10(psd_ds)
        predictor = torch.ones([psd_dB.shape[0], 2])
        predictor[:, 1] = torch.log10(edges[1:])
        p = torch.linalg.lstsq(predictor, psd_dB).solution
        noise_fit_dB = p[0] + log_f * p[1]
        return noise_fit_dB
