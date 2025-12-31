from typing import Optional

EXTERNAL_HOST = "10.1.1.0"
LOCAL_HOST = "127.0.0.1"
FRONTEND_ADDRESS = 'inproc://bridge'

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
    return f"inproc://control-{thread_id}"

def get_thread_name(block_name: Optional[str], thread_id: Optional[str]):
    if block_name is not None:
        thread_name = f"{block_name}-{thread_id}"
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
