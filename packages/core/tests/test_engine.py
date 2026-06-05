from __future__ import annotations

from edera_core.engine import Engine


def test_engine_without_registry(tmp_path):
    engine = Engine(tmp_path / "config")

    assert not hasattr(engine.bootstrap, "handler_registry")
    assert not hasattr(engine.bootstrap, "entity_type_registry")
