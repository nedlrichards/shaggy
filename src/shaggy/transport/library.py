from enum import Enum
from typing import Optional

from shaggy.proto.command_pb2 import Command
from shaggy.proto.channel_levels_pb2 import ChannelLevels
from shaggy.proto.stft_pb2 import STFT

EXTERNAL_HOST = "10.0.0.10"
LOCAL_HOST = "127.0.0.1"
FRONTEND_ADDRESS = 'inproc://bridge'


class BlockName(str, Enum):
    Heartbeat = "heartbeat"
    HeartbeatSrc = "heartbeat-src"
    GStreamerSrc = "gstreamer-src"
    ChannelLevels = "channel-levels"
    ShortTimeFFT = "short-time-fft"


TRANSPORT_TOPICS = {
        BlockName.Heartbeat.value: Command,
        BlockName.ChannelLevels.value: ChannelLevels,
        BlockName.ShortTimeFFT.value: STFT,
}

def get_address_from_cfg(cfg):
    address_type = cfg['global']['network']
    return get_address(address_type)

def get_address(address_type):
    if address_type == 'external':
        address = EXTERNAL_HOST
    elif address_type == 'local':
        address = LOCAL_HOST
    else:
        raise ValueError(f"address specification {address} not reckognized.")
    return address

def get_control_socket(thread_id):
    if thread_id == "":
        return f"inproc://control-{BlockName.Heartbeat.value}"
    else:
        return f"inproc://control-{thread_id}"

def get_thread_name(block_name: Optional[str], thread_id: Optional[str]):
    if block_name is not None:
        if thread_id is not None and len(thread_id) > 0:
            thread_name = f"{block_name}-{thread_id}"
        else:
            thread_name = block_name
    else:
        thread_name = None
    return thread_name


def get_block_socket(block_name, thread_id):
    thread_name = get_thread_name(block_name, thread_id)
    return f"inproc://{thread_name}"

def get_bridge_connection(address):
    return f"tcp://{address}:8100"

def get_command_connection(address):
    return f"tcp://{address}:8800"


class ThreadIDGenerator:
    def __init__(self):
        self.thread_id = 0

    def __call__(self):
        thread_id = self.thread_id
        self.thread_id += 1
        return f"{thread_id:05d}"
