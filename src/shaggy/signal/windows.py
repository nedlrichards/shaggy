"""
Both discretized and continous calculations of 'good' windows.

These are calculated with as generalized cosines, and are discussed in:
    Heinzel G. et al., “Spectrum and spectral density estimation by the Discrete Fourier transform (DFT),
    including a comprehensive list of window functions and some new flat-top windows”,
    February 15, 2002 https://holometer.fnal.gov/GH_FFT.pdf

Nuttall windows are made using the standard trade off between frequency and time resolution, HFT windows are
flat topped in the frequency domain and are designed for accurate amplitude measurements.
"""

from math import pi

import torch
from torch import Tensor

WINDOWS = {
    "HAMMING": [0.54, 0.46],
    "NUTTALL_3B": [0.4243801, 0.4973406, 0.0782793],
    "NUTTALL_4C": [0.3635819, 0.4891775, 0.1365995, 0.0106411],
    "HFT70": [1, 1.90796, 1.07349, 0.18199],
}

DEFAULT_DEVICE = torch.device("cpu")


def discretized(
    num_samples: int,
    window: str = "NUTTALL_3B",
    dtype: torch.dtype = torch.float32,
    device: torch.device = DEFAULT_DEVICE,
) -> Tensor:
    """
    Sample evenly over window duration.

    Args:
        num_samples: Number of samples used in window.
        window: Specifier of the window, must match a key in local WINDOWS dictionary.
    """
    phase = (
        2.0 * pi * torch.arange(num_samples, dtype=dtype, device=device) / num_samples
        - pi
    )
    return _general_cosine(phase, window)


def continous(sample_positions: Tensor, window: str = "NUTTALL_3B") -> Tensor:
    """
    Window calculated a specified samples positions along a window duration of (-0.5, 0.5].

    This duration is periodic, and samples outside the duration will be wrapped without error.

    Args:
        sample_positions: Normalized sample positions, which are wrapped to a range of (-0.5, 0.5].
            Shape is (...,num_samples).
        window: Specifier of the window, must match a key in local WINDOWS dictionary.
    """
    phase = 2.0 * pi * sample_positions
    return _general_cosine(phase, window)


def _general_cosine(phase: Tensor, window: str) -> Tensor:
    """
    Geralized cosine window calculation.

    https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.windows.general_cosine.html
    """
    weights = torch.tensor(WINDOWS[window], device=phase.device, dtype=phase.dtype)
    order = torch.arange(len(weights), device=phase.device, dtype=phase.dtype)
    window = torch.sum(
        weights[..., :] * torch.cos(order[..., :] * phase.unsqueeze(-1)), dim=-1
    )
    return window
