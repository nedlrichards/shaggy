import sys
import threading
import click
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QTabWidget, QWidget

from shaggy.widgets.channel_levels import AcousticChannels
from shaggy.widgets.camera_status_bar import CameraStatusBar
from shaggy.widgets.spectra import SpectraWidget
from shaggy.transport.host_bridge import HostBridge
from shaggy.transport import library
from shaggy.transport.thread_id_generator import ThreadIDGenerator

from shaggy.proto.command_pb2 import Command
from omegaconf import OmegaConf
stft_cfg = {
        'window_length': 12000,
        'stride_length': 6000,
        'window_spec': "HAMMING",
        'scaling_spec': "psd", 
        }
CFG = {'gstreamer_src': {'sample_rate': 48000, 'channels': 8}, 'stft': stft_cfg}



class MainWindow(QMainWindow):

    def __init__(self, address):
        super().__init__()
        self.setGeometry(100, 100, 1400, 800)
        self.setWindowTitle('Acoustic Camera')

        self.host_bridge = HostBridge(address)
        t = threading.Thread(target=self.host_bridge.run, daemon=True)
        t.start()
        self.thread_id_generator = ThreadIDGenerator()

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        audio_hbox = QHBoxLayout()
        central_widget.setLayout(audio_hbox)

        self.status_bar = CameraStatusBar(self.host_bridge, self)
        self.setStatusBar(self.status_bar)
        self.status_bar.heartbeat_status.heartbeat.status.connect(self._on_heartbeat_status)
        self.tabs = QTabWidget()
        audio_hbox.addWidget(self.tabs)
        self._tabs_initialized = False

        self.status_bar.record_button.clicked.connect(self._toggle_record)
        self.show()

    def _on_heartbeat_status(self, heartbeat_status: bool) -> None:
        if heartbeat_status and not self._tabs_initialized:
            self._init_tabs()

    def _init_tabs(self) -> None:
        self.channel_levels = AcousticChannels(CFG, self.thread_id_generator, self.host_bridge)
        self.status_bar.record_button.setEnabled(True)
        psd_thread_id = self.thread_id_generator()
        command = Command()
        command.command = "startup"
        command.thread_id = psd_thread_id
        command.block_name = library.BlockName.ShortTimeFFT.value
        command.config = OmegaConf.to_yaml(CFG)
        self.host_bridge.worker_hub.add_worker(command)
        self.spectra = SpectraWidget(
            CFG,
            self.host_bridge,
            psd_thread_id,
        )
        self.tabs.addTab(self.channel_levels, "channels")
        self.tabs.addTab(self.spectra, "specta")
        self._tabs_initialized = True

    def _toggle_record(self, checked: bool) -> None:
        command = Command()
        command.command = "start-record" if checked else "stop-record"
        command.block_name = library.BlockName.GStreamerSrc.value
        command.thread_id = self.channel_levels.gstreamer_thread_id
        self.host_bridge.worker_hub.send_command(command)

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
