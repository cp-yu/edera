from __future__ import annotations

from edera_core.engine import Engine


def test_engine_initializes_empty_bootstrap(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.toml").write_text("", encoding="utf-8")
    engine = Engine(config_dir)

    assert engine.bootstrap.manifests == []
    assert engine.bootstrap.storage_tables == {}
    assert engine.bootstrap.table_names == {}
    assert engine.bootstrap.extension_roots == {}
