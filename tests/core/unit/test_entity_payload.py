from __future__ import annotations

from edera_core.config.entities import EntityStore
from edera_core.config.schema import (
    EntitiesConfig,
    EntityConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
)
from edera_core.server import _entity_payload
from edera_core.storage.entities import DagRun
import pytest


def _stock_type() -> EntityTypeConfig:
    return EntityTypeConfig(
        display_name="Stock",
        business_id_field="code",
        display_template="{code} {name}",
        schema_={"type": "object", "properties": {"code": {"type": "string"}, "name": {"type": "string"}}},
    )


def _store(entity_types: dict[str, EntityTypeConfig] | None = None) -> EntityStore:
    return EntityStore(
        EntitiesConfig(entities=[]),
        entity_types or {"stock": _stock_type()},
        EntityRelationsConfig(relations=[]),
        None,
    )


def _entity(**attrs: object) -> EntityConfig:
    defaults = {"code": "00700.HK", "name": "Tencent"}
    defaults.update(attrs)
    return EntityConfig(id="stock-test", type="stock", attributes=defaults)


def test_includes_display():
    result = _entity_payload(_store(), _entity())
    assert result["display"] == "00700.HK Tencent"


def test_includes_ref():
    result = _entity_payload(_store(), _entity())
    assert result["ref"] == "stock:00700.HK"


def test_display_fallback_on_missing_template_key():
    entity = _entity(name=None)
    entity.attributes.pop("name", None)
    result = _entity_payload(_store(), entity)
    assert "display" in result
    assert result["display"]


def test_display_fallback_when_no_matching_entity_type():
    other_type = EntityTypeConfig(
        display_name="Other",
        business_id_field="id",
        display_template="{id}",
        schema_={"type": "object"},
    )
    result = _entity_payload(_store(entity_types={"other": other_type}), _entity())
    assert result["display"] == result["ref"]


def test_dag_run_startup_source_rejected():
    with pytest.raises(ValueError, match="source must be manual, retry, or trigger:<name>"):
        DagRun.model_validate({"run_id": "run-1", "source": "startup", "status": "running"})
