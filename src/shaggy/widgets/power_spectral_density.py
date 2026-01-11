import numpy as np
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from omegaconf import OmegaConf

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from shaggy.workers.power_spectral_density import PowerSpectralDensity


class PowerSpectralDensityWidget(QWidget):
    def __init__(
        self,
        cfg,
        thread_id_generator,
        host_bridge,
        num_windows: int = 10,
        window_hop: int = 1,
    ):
        super().__init__()
        self.host_bridge = host_bridge
        self.thread_id = thread_id_generator()
        self.sample_rate = cfg["gstreamer_src"]["sample_rate"]

        command = Command()
        command.command = "startup"
        command.thread_id = self.thread_id
        command.block_name = library.BlockName.ShortTimeFFT.value
        command.config = OmegaConf.to_yaml(cfg)
        self.host_bridge.command_hub.add_worker(command)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(1, 1, 1)
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("PSD (dB)")
        self.line = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.worker = PowerSpectralDensity(
            num_windows=num_windows,
            window_hop=window_hop,
            host_bridge=host_bridge,
            thread_id=self.thread_id,
        )
        self.worker.psd_ready.connect(self.update_psd)

    @Slot(object)
    def update_psd(self, psd) -> None:
        if isinstance(psd, (bytes, bytearray)):
            psd = np.frombuffer(psd, dtype=np.float64)
        psd = np.asarray(psd)
        if psd.size == 0:
            return

        freqs = np.linspace(0.0, self.sample_rate / 2.0, psd.size, dtype=np.float64)
        if self.line is None or self.line.get_xdata().size != psd.size:
            self.axes.cla()
            self.axes.set_xlabel("Frequency (Hz)")
            self.axes.set_ylabel("PSD (dB)")
            (self.line,) = self.axes.plot(freqs, psd)
            self.axes.set_xlim(0.0, freqs[-1])
        else:
            self.line.set_ydata(psd)
        self.canvas.draw_idle()
