from pathlib import Path

from edera_core.config.loader import load_app_config


def test_load_app_config_uses_empty_runtime_entities() -> None:
    config = load_app_config(Path("config"))

    assert "stock" in config.entity_types
    assert config.entities.entities == []
