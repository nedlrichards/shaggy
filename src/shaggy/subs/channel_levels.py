import numpy as np

from shaggy.subs.stft_buffer import STFTBuffer, STFTBufferConfig

UPDATE_PERIOD = 0.1

class ChannelLevels():
    """Transform streaming data to kernel strided data."""

    def __init__(self, sample_rate: int, num_channels: int):
        """Setup kernel transform."""
        self.num_channels = num_channels
        self.sample_rate = sample_rate
        self.stride_length = int(sample_rate * UPDATE_PERIOD)
        self.window_length = int(sample_rate * UPDATE_PERIOD)
        self.device = 'cpu'
        stft_buffer_config = STFTBufferConfig(
                stride_length=self.stride_length,
                window_length=self.window_length,
                num_channels=self.num_channels,
                device=self.device,
                )
        self.stft_buffer = STFTBuffer(stft_buffer_config)


    @classmethod
    def from_cfg(cls, cfg):
        """Initilize class instance from keywords."""
        return cls(
                sample_rate=cfg['gstreamer_src']['sample_rate'],
                num_channels=cfg['gstreamer_src']['channels'],
                )

    def __call__(self, msg: bytes):
        samples = self.stft_buffer(msg)
        if samples is None:
            return None

        samples_dB = 20 * np.log10(abs(samples.numpy()) + np.spacing(1.))
        samples_dB = samples_dB.max(axis=-1).astype(np.float32)

        return samples_dB
