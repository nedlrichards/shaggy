#!/usr/bin/env -S uv run

import os
import sys

os.environ["QT_API"] = "PySide6"

from contextlib import contextmanager, ExitStack
import time

import hydra
from hydra.utils import instantiate
from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtCore import QObject, Signal, QThread, QRunnable, Slot, QThreadPool
from omegaconf import DictConfig, OmegaConf
import zmq

from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure

from shaggy.caps.acoustic_src import AcousticSrc
from shaggy.signal.short_time_fft import ShortTimeFFT


class MplCanvas(FigureCanvas):
    subscriber_thread = None

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)

    def update(self, stft_proto):
        pass



class SubscriberThread(QRunnable, QObject):
    new_message = Signal(bytes)
    finished_signal = Signal(None)

    def __init__(self, sub_address):
        QRunnable.__init__(self)
        QObject.__init__(self)

        self.context = zmq.Context.instance()
        self.sub_address = sub_address
        self.sub_topic = ""
        self.finished = False
        self.finished_signal.connect(self.stop_run)

        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect(self.sub_address)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, self.sub_topic)
        self.sub.setsockopt(zmq.RCVTIMEO, 100)

    @Slot()
    def run(self):
        while not self.finished:
            try:
                topic, ts_bytes, stft_msg = self.sub.recv_multipart()
            except zmq.error.Again:
                continue
            else:
                print('Hello')
                self.new_message.emit(stft_msg)

    @Slot()
    def stop_run(self):
        print('finishing stft')
        self.finished = True


class MainWindow(QMainWindow):

    def __init__(self, cfg):
        super().__init__()
        self.stft_address = "inproc://stft"
        self.sc = MplCanvas(self, width=5, height=4, dpi=100)
        self.threadpool= QThreadPool()
        self.stft_sub = None
        self.start_sub_thread()
        self.show()

    def start_sub_thread(self):
        self.stft_sub = SubscriberThread(self.stft_address)
        self.stft_sub.new_message.connect(self.receive_stft)
        self.threadpool.start(self.stft_sub)

    def receive_stft(self, stft_msg: bytes):
        print('received stft')
        self.sc.ax.plot([0,1,2,3,4], [10,1,20,3,40])
        self.setCentralWidget(self.sc)
        self.show()

    def closeEvent(self, event):
        if self.stft_sub is not None:
            self.stft_sub.finished_signal.emit()

def main(cfg):
    app = QApplication(sys.argv)
    w = MainWindow(cfg)
    app.exec()


@hydra.main(version_base=None, config_path="conf", config_name="config")
def my_app(cfg : DictConfig) -> None:
    main(cfg)

if __name__ == "__main__":
    my_app()
