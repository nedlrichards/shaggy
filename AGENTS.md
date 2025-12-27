**Project Overview**
- Python 3.10 application for acoustic data collection and processing.
- Primary code lives under `src/shaggy/` with Hydra config in `conf/`.

**Repository Layout**
- `src/shaggy/bin/`: CLI entry points (`camera`, `controller`).
- `src/shaggy/signal/`, `src/shaggy/blocks/`, `src/shaggy/subs/`: signal processing and pipeline blocks.
- `src/shaggy/proto/`: protobuf schemas and generated Python stubs.
- `conf/`: Hydra configs for sources, STFT, and collection.
- `tools/build_protos.py`: regenerates protobuf Python stubs with `protoc`.

**Common Commands**
- Install deps (uv): `uv sync`
- Run camera app: `uv run camera`
- Run controller app: `uv run controller`
- Regenerate protobufs: `uv run tools/build_protos.py`

**Notes**
- Python version is pinned in `pyproject.toml` (3.10.x).
- Generated protobufs are committed in `src/shaggy/proto/`; update them when `.proto` files change.
