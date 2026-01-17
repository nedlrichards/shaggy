import time

import numpy as np
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from omegaconf import OmegaConf

from shaggy.proto.command_pb2 import Command
from shaggy.transport import library
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from shaggy.workers.power_spectral_density import PowerSpectralDensity


class PowerSpectralDensityWidget(QWidget):
    def __init__(
        self,
        cfg,
        host_bridge,
        thread_id: str,
        thread_id_generator=None,
        num_windows: int = 10,
        window_hop: int = 1,
    ):
        super().__init__()
        self.cfg = cfg
        self.host_bridge = host_bridge
        self.thread_id = thread_id
        self.thread_id_generator = thread_id_generator
        self.sample_rate = cfg["gstreamer_src"]["sample_rate"]
        self.num_channels = self.cfg["gstreamer_src"]["channels"]
        self.channel_idx = None
        self._noise_floor_worker = None
        self._noise_floor_thread_id = None

        num_freq = cfg["stft"]["window_length"] // 2 + 1
        f_axis = np.arange(num_freq) / cfg["stft"]["window_length"]
        self.f_axis = f_axis * self.sample_rate

        self.figure = Figure()
        self.figure.subplots_adjust(right=0.875)
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(1, 1, 1)
        self.axes.set_xlabel("Frequency (Hz)")
        self.axes.set_ylabel("PSD (dB)")
        self.line = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, 1)
        button_layout = QVBoxLayout()
        self.noise_floor_button = QPushButton("noise floor")
        button_layout.addWidget(self.noise_floor_button)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
        self.noise_floor_button.clicked.connect(self._request_noise_floor)

        self.worker = PowerSpectralDensity(
            num_windows=num_windows,
            window_hop=window_hop,
            host_bridge=host_bridge,
            thread_id=self.thread_id,
        )
        self.worker.psd_ready.connect(self.update_psd)

    @Slot()
    def _request_noise_floor(self) -> None:
        noise_floor_thread_id = self.thread_id_generator()
        command = Command()
        command.command = "startup"
        command.thread_id = noise_floor_thread_id
        command.block_name = library.BlockName.NoiseFloor.value
        command.config = OmegaConf.to_yaml(self.cfg)
        self.host_bridge.command_hub.add_worker(command)

        self._noise_floor_thread_id = noise_floor_thread_id
        self._noise_floor_worker = self.host_bridge.command_hub.get_worker(
            library.BlockName.NoiseFloor.value,
            noise_floor_thread_id,
        )
        self._noise_floor_worker.content_msg.connect(self._handle_noise_floor)

    @Slot(bytes, bytes, bytes)
    def _handle_noise_floor(self, topic, timestamp, msg) -> None:
        self._noise_floor_worker.content_msg.disconnect(self._handle_noise_floor)
        command = Command()
        command.command = "shutdown"
        command.thread_id = self._noise_floor_thread_id
        command.block_name = library.BlockName.NoiseFloor.value
        self.host_bridge.command_hub.remove_worker(command)
        self._noise_floor_worker = None
        self._noise_floor_thread_id = None

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
            self.axes.set_ylim(-110.0, -50.)
        else:
            self.line.set_ydata(psd_dB[1:])
        self.canvas.draw_idle()
