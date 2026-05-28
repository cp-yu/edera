from __future__ import annotations

import grpc
import pytest

from edera_core.config_service import _ConfigService
from edera_core.proto import edera_pb2 as pb2

from service_fakes import AbortError, FakeContext, FakeDaemon


@pytest.mark.asyncio
async def test_delete_entity_type_no_cascade(tmp_path):
    root = tmp_path / "config"
    _write_config(root)
    service = _ConfigService(FakeDaemon(root))

    with pytest.raises(AbortError) as exc:
        await service.DeleteEntityType(pb2.DeleteEntityTypeRequest(name="stock", cascade=False), FakeContext())

    assert exc.value.code == grpc.StatusCode.FAILED_PRECONDITION


@pytest.mark.asyncio
async def test_save_system_protected(tmp_path):
    root = tmp_path / "config"
    _write_config(root, protected=True)
    service = _ConfigService(FakeDaemon(root))

    with pytest.raises(AbortError) as exc:
        await service.SaveEntityType(pb2.ConfigFileContentRequest(name="stock", content=_entity_type()), FakeContext())

    assert exc.value.code == grpc.StatusCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_save_invalid_system_config(tmp_path):
    root = tmp_path / "config"
    _write_config(root)
    service = _ConfigService(FakeDaemon(root))

    with pytest.raises(AbortError) as exc:
        await service.SaveSystemConfig(pb2.TextRequest(content="schedule_minutes = 0\n"), FakeContext())

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


def _write_config(root, protected=False):
    (root / "dags").mkdir(parents=True)
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(_entity_type(protected), encoding="utf-8")
    (root / "entities.yaml").write_text("entities:\n- id: s1\n  type: stock\n  attributes:\n    code: AAPL\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text("database_url = \"sqlite+aiosqlite:///tmp/test.db\"\nschedule_minutes = 1\n", encoding="utf-8")


def _entity_type(protected=False):
    suffix = "system_protected: true\n" if protected else ""
    return "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema:\n  properties:\n    code: {}\n" + suffix
