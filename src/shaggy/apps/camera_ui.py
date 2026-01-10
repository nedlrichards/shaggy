import sys
import threading
import click
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from shaggy.widgets.channel_levels import AcousticChannels
from shaggy.widgets.heartbeat import HeartbeatStatus
from shaggy.transport.host_bridge import HostBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator


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

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        audio_hbox = QHBoxLayout()
        central_widget.setLayout(audio_hbox)

        # add a permanent widget to the status bar
        host_bridge = HostBridge(address)
        t = threading.Thread(target=host_bridge.run, daemon=True)
        t.start()

        stft_cfg = {
                'window_length': 12000,
                'stride_length': 6000,
                'window_spec': "HAMMING",
                'scaling_spec': "psd", 
                }
        cfg = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}

        thread_id_generator = ThreadIDGenerator()
        self.heartbeat_status = HeartbeatStatus(thread_id_generator, host_bridge)
        self.channel_levels = AcousticChannels(cfg, thread_id_generator, host_bridge)
        audio_hbox.addWidget(self.channel_levels)

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
