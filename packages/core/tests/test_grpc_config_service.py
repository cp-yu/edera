from __future__ import annotations

from edera_core.config_service import _ConfigService
from edera_core.proto import edera_pb2_grpc as pb2_grpc


def test_reload_rpcs_are_absent():
    assert not hasattr(_ConfigService, "ReloadEntityTypes")
    assert not hasattr(_ConfigService, "ReloadSkills")
    assert not hasattr(pb2_grpc.ConfigServiceStub, "ReloadEntityTypes")
    assert not hasattr(pb2_grpc.ConfigServiceStub, "ReloadSkills")
