import sys
import threading
import click
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QTabWidget, QWidget

from shaggy.widgets.channel_levels import AcousticChannels
from shaggy.widgets.heartbeat_status import HeartbeatStatus
from shaggy.widgets.power_spectral_density import PowerSpectralDensityWidget
from shaggy.transport.host_bridge import HostBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator

stft_cfg = {
        'window_length': 12000,
        'stride_length': 6000,
        'window_spec': "HAMMING",
        'scaling_spec': "psd", 
        }
CFG = {'gstreamer_src': {'sample_rate': 48000, 'channels': 2}, 'stft': stft_cfg}



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

        self.thread_id_generator = ThreadIDGenerator()
        self.host_bridge = host_bridge
        self.heartbeat_status = HeartbeatStatus(host_bridge)
        self.heartbeat_status.heartbeat.status.connect(self._on_heartbeat_status)
        self.tabs = QTabWidget()
        audio_hbox.addWidget(self.tabs)
        self._tabs_initialized = False

        self.status_bar.addPermanentWidget(self.heartbeat_status)
        self.show()

    def set_title(self, filename=None):
        title = f"{filename if filename else 'Untitled'} - {self.title}"
        self.setWindowTitle(title)

    def _on_heartbeat_status(self, heartbeat_status: bool) -> None:
        if heartbeat_status and not self._tabs_initialized:
            self._init_tabs()

    def _init_tabs(self) -> None:
        self.channel_levels = AcousticChannels(CFG, self.thread_id_generator, self.host_bridge)
        self.power_spectral_density = PowerSpectralDensityWidget(
            CFG,
            self.thread_id_generator,
            self.host_bridge,
        )
        self.tabs.addTab(self.channel_levels, "channels")
        self.tabs.addTab(self.power_spectral_density, "specta")
        self._tabs_initialized = True

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
