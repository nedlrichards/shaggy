import sys

import click
from PySide6.QtWidgets import QApplication, QMainWindow

from omegaconf import OmegaConf
from shaggy.proto.command_pb2 import Command
from shaggy.widgets.heartbeat import HeartbeatStatus
from shaggy.transport.host_bridge import HostBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft


class MainWindow(QMainWindow):

    def __init__(self, address):
        super().__init__()

        self.setGeometry(100, 100, 500, 300)

        self.title = 'Acoustic Camera'
        self.set_title()

        self.path = None

        # status bar
        self.status_bar = self.statusBar()

        # display the a message in 5 seconds
        self.status_bar.showMessage('Ready', 5000)

        # add a permanent widget to the status bar
        host_bridge = HostBridge(address)
        thread_id_generator = ThreadIDGenerator()

        stft_cfg = {
                'window_length': 12000,
                'stride_length': 6000,
                'window_spec': "HAMMING",
                'scaling_spec': "psd", 
                }
        cfg = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}

        self.heartbeat_status = HeartbeatStatus(address, host_bridge)

        command = Command()
        command.command = 'startup'
        command.thread_id = thread_id_generator()
        command.block_name = heartbeat.BLOCK_NAME
        command.config = OmegaConf.to_yaml(OmegaConf.create(cfg))

        host_bridge.send_command(command)

        command.thread_id = thread_id_generator()
        command.block_name = gstreamer_src.BLOCK_NAME

        host_bridge.send_command(command)

        command.thread_id = thread_id_generator()
        command.block_name = channel_levels.BLOCK_NAME

        host_bridge.send_command(command)

        command.thread_id = thread_id_generator()
        command.block_name = short_time_fft.BLOCK_NAME

        host_bridge.send_command(command)

        self.status_bar.addPermanentWidget(self.heartbeat_status)
        self.show()


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
