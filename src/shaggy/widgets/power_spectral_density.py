import numpy as np
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from shaggy.workers.power_spectral_density import PowerSpectralDensity


class PowerSpectralDensityWidget(QWidget):
    def __init__(
        self,
        cfg,
        host_bridge,
        thread_id: str,
        num_windows: int = 10,
        window_hop: int = 1,
        channel_idx: int | None = None,
    ):
        super().__init__()
        self.cfg = cfg
        self.host_bridge = host_bridge
        self.thread_id = thread_id
        self.sample_rate = cfg["gstreamer_src"]["sample_rate"]
        self.num_channels = self.cfg["gstreamer_src"]["channels"]
        if channel_idx is not None and not 0 <= channel_idx < self.num_channels:
            raise ValueError(
                f"channel_idx must be in [0, {self.num_channels - 1}], got {channel_idx}"
            )
        self.channel_idx = channel_idx

        num_freq = cfg["stft"]["window_length"] // 2 + 1
        f_axis = np.arange(num_freq) / cfg["stft"]["window_length"]
        self.f_axis = f_axis * self.sample_rate

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(1, 1, 1)
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("PSD (dB)")
        self.line = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, 1)

        self.worker = PowerSpectralDensity(
            num_windows=num_windows,
            window_hop=window_hop,
            host_bridge=host_bridge,
            thread_id=self.thread_id,
        )
        self.worker.psd_ready.connect(self.update_psd)

    def set_channel_idx(self, channel_idx: int | None) -> None:
        self.channel_idx = channel_idx

    @Slot(object)
    def update_psd(self, psd) -> None:
        psd = np.asarray(psd)
        if psd.ndim == 2:
            if self.channel_idx is None:
                psd = psd.mean(axis=-1)
            else:
                psd = psd[:, self.channel_idx]
        psd_dB = 10 * np.log10(psd + 1e-11)

        if self.line is None:
            self.axes.cla()
            self.line, = self.axes.semilogx(self.f_axis[1:], psd_dB[1:])
            self.axes.set_xlim(10.0, self.f_axis[-1])
            self.axes.set_ylim(-80.0, 0.)
        else:
            self.line.set_ydata(psd_dB[1:])
        self.canvas.draw_idle()
