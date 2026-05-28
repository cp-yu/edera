#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

uv run python -m grpc_tools.protoc \
  -I proto \
  --python_out=packages/core/src/edera_core/proto \
  --grpc_python_out=packages/core/src/edera_core/proto \
  proto/edera.proto

python - <<'PY'
from pathlib import Path

path = Path("packages/core/src/edera_core/proto/edera_pb2_grpc.py")
text = path.read_text(encoding="utf-8")
text = text.replace("import edera_pb2 as edera__pb2", "from edera_core.proto import edera_pb2 as edera__pb2")
path.write_text(text, encoding="utf-8")
PY
