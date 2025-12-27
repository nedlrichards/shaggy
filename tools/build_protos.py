#!/usr/bin/env -S uv run

import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROTO_DIR = ROOT / "src/shaggy/proto"

proto_files = [
    "samples.proto",
    "stft.proto",
    "detections.proto",
    "command.proto",
    "channel_levels.proto",
]

for proto in proto_files:
    subprocess.check_call([
        "protoc",
        f"--proto_path={PROTO_DIR}",
        f"--python_out={PROTO_DIR}",
        str(PROTO_DIR / proto),
    ])
