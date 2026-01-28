import torch

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

