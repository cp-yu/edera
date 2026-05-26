from __future__ import annotations

import importlib
import sys
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from grpc_tools import protoc


@dataclass(frozen=True)
class RigProto:
    pb2: object
    pb2_grpc: object


@lru_cache(maxsize=1)
def load_rig_proto() -> RigProto:
    proto_dir = Path(__file__).resolve().parents[4] / "proto"
    out_dir = Path(tempfile.gettempdir()) / "stockimformation-rig-grpc"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = protoc.main(
        [
            "grpc_tools.protoc",
            "-I",
            str(proto_dir),
            f"--python_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            str(proto_dir / "rig.proto"),
        ]
    )
    if result != 0:
        raise RuntimeError("failed to compile proto/rig.proto")
    if str(out_dir) not in sys.path:
        sys.path.insert(0, str(out_dir))
    return RigProto(importlib.import_module("rig_pb2"), importlib.import_module("rig_pb2_grpc"))
