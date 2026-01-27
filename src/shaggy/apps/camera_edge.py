#!/usr/bin/env -S uv run

import threading
import time
import shutil
import subprocess

import click
import zmq

from shaggy.transport.edge_bridge import EdgeBridge
from shaggy.transport import library

@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    # Prime the SSL 18 USB interface so subsequent 8ch capture is valid.
    process = ["arecord", "-D", "hw:S18,0", "-c", "26", "-f", "S32_LE", "-r", "48000", "-d", "1", "/dev/null"]
    subprocess.run(process, check=False)
    address = library.get_address(address_type)
    edge_bridge = EdgeBridge(address)
    edge_bridge.run()

if __name__ == "__main__":
    my_app()
