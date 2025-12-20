
EXTERNAL_HOST = "10.1.1.0"
LOCAL_HOST = "127.0.0.1"

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
