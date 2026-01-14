from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from shaggy.widgets.power_spectral_density import PowerSpectralDensityWidget
from shaggy.widgets.spectrogram import SpectrogramWidget


class SpectraWidget(QWidget):
    def __init__(
        self,
        cfg,
        host_bridge,
        thread_id: str,
        num_windows: int = 1,
        window_hop: int = 1,
    ):
        super().__init__()
        self.cfg = cfg
        self.host_bridge = host_bridge
        self.thread_id = thread_id
        self.num_channels = cfg["gstreamer_src"]["channels"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        plots_layout = QVBoxLayout()
        self.spectrogram = SpectrogramWidget(
            cfg,
            host_bridge,
            thread_id,
            num_windows=num_windows,
            window_hop=window_hop,
        )
        self.power_spectral_density = PowerSpectralDensityWidget(
            cfg,
            host_bridge,
            thread_id,
            num_windows=num_windows,
            window_hop=window_hop,
            channel_idx=None,
        )
        plots_layout.addWidget(self.spectrogram)
        plots_layout.addWidget(self.power_spectral_density)
        layout.addLayout(plots_layout, 1)

        channel_group = QGroupBox("Channel")
        channel_layout = QVBoxLayout(channel_group)
        self.channel_buttons = QButtonGroup(channel_group)
        avg_button = QRadioButton("Average")
        avg_button.setChecked(True)
        self.channel_buttons.addButton(avg_button, -1)
        channel_layout.addWidget(avg_button)
        for idx in range(self.num_channels):
            button = QRadioButton(f"Channel {idx}")
            self.channel_buttons.addButton(button, idx)
            channel_layout.addWidget(button)
        channel_layout.addStretch(1)
        self.channel_buttons.idClicked.connect(self._set_channel_idx)
        layout.addWidget(channel_group)

    @Slot(int)
    def _set_channel_idx(self, channel_id: int) -> None:
        channel_idx = None if channel_id < 0 else channel_id
        self.spectrogram.set_channel_idx(channel_idx)
        self.power_spectral_density.set_channel_idx(channel_idx)
