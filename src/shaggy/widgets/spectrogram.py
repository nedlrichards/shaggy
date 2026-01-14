from math import ceil
import numpy as np
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from shaggy.workers.power_spectral_density import PowerSpectralDensity


class SpectrogramWidget(QWidget):
    def __init__(
        self,
        cfg,
        host_bridge,
        thread_id: str,
        num_windows: int = 1,
        window_hop: int = 1,
        time_span_s: float = 60.,
        num_blocks: int = 6,
    ):
        super().__init__()
        self.cfg = cfg
        self.host_bridge = host_bridge
        self.thread_id = thread_id
        self.num_windows = num_windows
        self.window_hop = window_hop
        self.time_span_s = time_span_s
        self.num_blocks = num_blocks
        self.channel_idx = None

        self.sample_rate = cfg["gstreamer_src"]["sample_rate"]
        self.num_channels = cfg["gstreamer_src"]["channels"]
        num_freq = cfg["stft"]["window_length"] // 2 + 1
        f_axis = np.arange(num_freq) / cfg["stft"]["window_length"]
        self.f_axis = (f_axis * self.sample_rate)
        self.time_step_s = cfg["stft"]["stride_length"] * self.window_hop / self.sample_rate

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(1, 1, 1)
        self.axes.set_xlabel("Time (s)")
        self.axes.set_ylabel("Frequency (Hz)")
        self.image = None
        self.buffer = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.worker = PowerSpectralDensity(
            num_windows=num_windows,
            window_hop=window_hop,
            host_bridge=host_bridge,
            thread_id=self.thread_id,
        )
        self.worker.psd_ready.connect(self.update_spectrogram)

        self.block_size = ceil(self.time_span_s / (self.time_step_s * self.num_blocks))
        self.block_shape = (self.block_size, self.num_channels, self.f_axis.size)
        self.sample_history = []
        for i in range(self.num_blocks):
            block = np.full(self.block_shape, -200, dtype=np.float32)
            self.sample_history.append(block)

        self.t_axis = np.arange(self.block_size * self.num_blocks, dtype=np.float32)
        self.t_axis *= self.time_step_s
        self.block_idx = 0
        self.sample_idx = 0
        initial_spectrogram = np.full(
            (self.f_axis.size, self.t_axis.size),
            -200,
            dtype=np.float32,
        )
        self.image = self.axes.pcolormesh(
            self.t_axis,
            self.f_axis,
            initial_spectrogram,
            vmin=-60.0,
            vmax=0.0,
            shading="auto",
        )
        self.axes.set_ylim(self.f_axis[0], 1000)
        self.num_skip = 10
        self.skip_idx = 0

    def _add_slice(self, psd) -> None:
        if self.sample_idx >= self.block_size:
            if self.block_idx < self.num_blocks - 1:
                self.block_idx += 1
                self.sample_idx = 0
            else:
                self.sample_history = self.sample_history[1:]
                block = np.full(self.block_shape, -200, dtype=np.float32)
                self.sample_history.append(block)
                self.sample_idx = 0

        current_block = self.sample_history[self.block_idx]
        current_block[self.sample_idx] = psd
        self.sample_idx += 1

    def _get_spectrogram(self) -> np.array:
        spectrogram = np.array(self.sample_history)
        spectrogram = np.reshape(spectrogram, (-1, self.num_channels, self.f_axis.size))
        return spectrogram
            
    def set_channel_idx(self, channel_idx: int | None) -> None:
        self.channel_idx = channel_idx

    @Slot(object)
    def update_spectrogram(self, psd) -> None:
        self._add_slice(psd)
        self.skip_idx += 1
        if self.skip_idx < self.num_skip:
            return
        self.skip_idx = 0
        spectrogram = self._get_spectrogram()
        if self.channel_idx is None:
            spectrogram = np.mean(spectrogram, axis=1)
        else:
            spectrogram = spectrogram[:, self.channel_idx]

        spectrogram_dB = 10 * np.log10(spectrogram + np.spacing(1.0, dtype=np.float32))
        self.image.set_array(spectrogram_dB.T.ravel())

        self.canvas.draw_idle()
