#!/usr/bin/env -S uv run

import signal
from threading import Event
import time

from contextlib import contextmanager, ExitStack

import hydra
from omegaconf import DictConfig, OmegaConf
import zmq

from shaggy.signal.short_time_fft import ShortTimeFFT

def get_exit_event():
    exit_event = Event()

    def quit_event(signo, _frame):
        print("Interrupted by %d, shutting down" % signo)
        exit_event.set()

    signal.signal(signal.SIGTERM, quit_event)
    signal.signal(signal.SIGINT, quit_event)
    signal.signal(signal.SIGHUP, quit_event)
    return exit_event

@hydra.main(version_base=None, config_path="../conf", config_name="config")
def my_app(cfg: DictConfig) -> None:
    exit_event = get_exit_event()
    short_time_fft = ShortTimeFFT.from_cfg(cfg)
    with short_time_fft.start_stft() as pipeline:
        exit_event.wait()

if __name__ == "__main__":
    my_app()
