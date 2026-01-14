import matplotlib
import numpy as np
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from omegaconf import OmegaConf

from shaggy.proto.command_pb2 import Command
from shaggy.proto.channel_levels_pb2 import ChannelLevels
from shaggy.transport import library

class MeterPackage(QWidget):
    """Sound meter for all channels."""

    class LevelMeter(QWidget):
        """Sound meter for one channel."""

        def __init__(self):
            """Setup sound meter display."""
            super().__init__()
            self.min_bar_height = 25
            self.setMinimumSize(0, self.min_bar_height)
            self.color_map = matplotlib.colormaps["YlOrRd"]
            self.max_db = 0.0
            self.min_db = -50.0
            self.level = self.min_db

        def setLevel(self, level):
            """Update meter."""
            self.level = level
            self.update()

        def paintEvent(self, event):
            """Refresh display."""
            normalized = (self.level - self.min_db) / (self.max_db - self.min_db)
            normalized = max(0.0, min(1.0, normalized))
            color = self.color_map(normalized)
            r = int(color[0] * 255)
            g = int(color[1] * 255)
            b = int(color[2] * 255)

            painter = QtGui.QPainter(self)
            bar_height = int(self.height() * normalized)
            painter.fillRect(
                0, self.height() - bar_height, 100, bar_height, QtGui.QColor(r, g, b)
            )

    def __init__(self, label):
        """Sound level display for all channels."""
        super().__init__()
        self.meter = self.LevelMeter()
        self.label = QLabel(label)
        self.label.setStyleSheet(
            "color: white; font-size: 20px; text-align: center; background-color: blue;"
        )
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)

        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.meter)
        box.addWidget(self.label)
        self.setLayout(box)


class AcousticChannels(QWidget):
    def __init__(self, cfg, thread_id_generator, host_bridge):
        super().__init__()
        self.cfg = cfg
        self.host_bridge = host_bridge

        yaml_cfg = OmegaConf.to_yaml(cfg)
        self.gstreamer_thread_id = thread_id_generator()
        command = Command()
        command.command = 'startup'
        command.thread_id = self.gstreamer_thread_id
        command.block_name = library.BlockName.GStreamerSrc.value
        command.config = yaml_cfg
        self.host_bridge.command_hub.add_worker(command)

        self.channel_levels_thread_id = thread_id_generator()
        command = Command()
        command.command = 'startup'
        command.thread_id = self.channel_levels_thread_id
        command.block_name = library.BlockName.ChannelLevels.value
        command.config = yaml_cfg
        self.host_bridge.command_hub.add_worker(command)
        self.worker = self.host_bridge.command_hub.get_worker(
            library.BlockName.ChannelLevels.value,
            self.channel_levels_thread_id,
        )
        self.worker.content_msg.connect(self.set_channel_levels)
        num_channels = self.cfg['gstreamer_src']['channels']
        self.meter_packages = [MeterPackage(str(i)) for i in range(num_channels)]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for meter in self.meter_packages:
            layout.addWidget(meter)
        self.setLayout(layout)

    @Slot(bytes, bytes, bytes)
    def set_channel_levels(self, topic, timestamp, msg):
        command = ChannelLevels()
        command.ParseFromString(msg)
        levels = np.frombuffer(command.levels, dtype=np.float32)
        for i, l in enumerate(levels):
            self.meter_packages[i].meter.setLevel(float(l))
