#!/usr/bin/env -S uv run

import threading
import time

import click
import zmq

from shaggy.transport.edge_bridge import EdgeBridge
from shaggy.transport import library

@click.command()
@click.option('--external', 'address_type', flag_value='external', default='external')
@click.option('--local', 'address_type', flag_value='local')
def my_app(address_type) -> None:
    address = library.get_address(address_type)
    edge_bridge = EdgeBridge(address)
    edge_bridge.run()

if __name__ == "__main__":
    my_app()
