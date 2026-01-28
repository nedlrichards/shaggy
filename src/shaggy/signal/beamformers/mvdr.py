import torch

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
