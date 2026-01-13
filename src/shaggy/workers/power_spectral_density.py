import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from shaggy.proto import stft_pb2
from shaggy.transport import library
from shaggy.transport.host_bridge import HostBridge


class PowerSpectralDensity(QObject):
    """Listen for STFT messages and emit PSD data (stubbed)."""

    psd_ready = Signal(object)

    def __init__(self,
                 num_windows: int,
                 window_hop: int,
                 host_bridge: HostBridge,
                 thread_id: str
                 ):
        super().__init__()
        self.num_windows = num_windows
        self.window_hop = window_hop
        self.host_bridge = host_bridge
        self.thread_id = thread_id
        self.worker = self.host_bridge.command_hub.get_worker(
            library.BlockName.ShortTimeFFT.value,
            self.thread_id,
        )
        self.worker.content_msg.connect(self._handle_stft)
        self.stft_windows = []

    @Slot(bytes, bytes, bytes)
    def _handle_stft(self, topic, timestamp, msg) -> None:
        stft_msg = stft_pb2.STFT()
        stft_msg.ParseFromString(msg)

        num_times = stft_msg.num_times_0
        num_channels = stft_msg.num_channel_2
        num_freq = stft_msg.num_fft // 2 + 1

        stft_flat = np.frombuffer(stft_msg.stft_samples, dtype=np.complex64)
        stft_samples = stft_flat.reshape((num_times, num_freq, num_channels))
        self.stft_windows += list(stft_samples)
        while len(self.stft_windows) > self.num_windows + self.window_hop:
            self.stft_windows = self.stft_windows[self.window_hop:]

        if len(self.stft_windows) < self.num_windows:
            return

        stft_ensample = np.array(self.stft_windows[:self.num_windows])
        psd = np.mean(abs(stft_ensample) ** 2, axis=(0, 2))

        self.psd_ready.emit(psd)
