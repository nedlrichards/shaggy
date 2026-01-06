import sys
import threading
import time

import click
import numpy as np
from PySide6 import QtCore
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget
import zmq

from omegaconf import OmegaConf
from shaggy.proto.command_pb2 import Command
from shaggy.proto import channel_levels_pb2
from shaggy.widgets.channel_levels import ChannelLevel
from shaggy.widgets.heartbeat import HeartbeatStatus
from shaggy.workers.channel_levels import ChannelLevelWorker
from shaggy.transport.host_bridge import HostBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft


class MainWindow(QMainWindow):

    def __init__(self, address):
        super().__init__()

        self.setGeometry(100, 100, 1000, 600)

        self.title = 'Acoustic Camera'
        self.set_title()

        self.path = None

        # status bar
        self.status_bar = self.statusBar()

        # display the a message in 5 seconds
        self.status_bar.showMessage('Ready', 5000)

        """
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        audio_hbox = QHBoxLayout()
        self.num_channels = 2
        self.sound_meter = [None] * self.num_channels
        self.sound_volume = np.zeros(16, dtype=np.float32)
        for i in range(self.num_channels):
            self.sound_meter[i] = ChannelLevel(str(i + 1))
            audio_hbox.addWidget(self.sound_meter[i])
        central_widget.setLayout(audio_hbox)

        self.channel_levels_worker = ChannelLevelWorker(address)
        self.channel_levels_thread = QThread()
        self.channel_levels_worker.moveToThread(self.channel_levels_thread)
        self.channel_levels_worker.message_received.connect(self.update_channel_levels)
        self.channel_levels_thread.started.connect(self.channel_levels_worker.run)
        self.channel_levels_thread.start()
        """

        # add a permanent widget to the status bar
        host_bridge = HostBridge(address)
        t = threading.Thread(target=host_bridge.run, daemon=True)
        t.start()
        thread_id_generator = ThreadIDGenerator()

        stft_cfg = {
                'window_length': 12000,
                'stride_length': 6000,
                'window_spec': "HAMMING",
                'scaling_spec': "psd", 
                }
        cfg = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}

        context = zmq.Context.instance()
        control_socket = context.socket(zmq.PAIR)
        control_socket.bind("inproc://host-control")

        command = Command()
        command.command = 'startup'
        command.thread_id = thread_id_generator()
        command.block_name = library.BlockName.Heartbeat.value
        command.config = OmegaConf.to_yaml(cfg)
        payload = command.SerializeToString()

        control_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        control_socket.send(payload)

        self.heartbeat_status = HeartbeatStatus(command.thread_id, host_bridge)

        #host_bridge.add_worker(library.BlockName.Heartbeat.value, thread_id_generator(), OmegaConf.create(cfg))

        """

        command.thread_id = thread_id_generator()
        command.block_name = library.BlockName.GStreamerSrc.value

        host_bridge.send_command(command)

        command.thread_id = thread_id_generator()
        command.block_name = library.BlockName.ChannelLevels.value

        host_bridge.send_command(command)

        command.thread_id = thread_id_generator()
        command.block_name = library.BlockName.ShortTimeFFT.value

        host_bridge.send_command(command)
        """

        self.status_bar.addPermanentWidget(self.heartbeat_status)
        self.show()

    @QtCore.Slot(bytes)
    def update_channel_levels(self, message: bytes) -> None:
        levels_msg = channel_levels_pb2.ChannelLevels()
        levels_msg.ParseFromString(message)
        if not levels_msg.HasField("num_channels_0"):
            return

        num_channels = levels_msg.num_channels_0
        levels = np.frombuffer(levels_msg.levels, dtype=np.float32)
        for idx, level in enumerate(levels):
            self.sound_meter[idx].setLevel(float(level))

    def set_title(self, filename=None):
        title = f"{filename if filename else 'Untitled'} - {self.title}"
        self.setWindowTitle(title)

@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    address = library.get_address(address_type)
    app = QApplication(sys.argv)
    window = MainWindow(address)
    sys.exit(app.exec())


if __name__ == '__main__':
    my_app()
