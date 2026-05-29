from __future__ import annotations

from pathlib import Path
from typing import Any

import grpc

from edera_core.proto import edera_pb2 as pb2


class AbortError(Exception):
    def __init__(self, code: grpc.StatusCode, details: str) -> None:
        self.code = code
        self.details = details


class FakeContext:
    def invocation_metadata(self) -> tuple[tuple[str, str], ...]:
        return (("x-edera-identity", "human:test"),)

    def auth_context(self) -> dict[str, list[bytes]]:
        return {}

    async def abort(self, code: grpc.StatusCode, details: str) -> None:
        raise AbortError(code, details)


class FakeDaemon:
    def __init__(self, config_dir: Path, controller: Any | None = None) -> None:
        self.config_dir = config_dir
        self.controller = controller
        self.pb2 = pb2
