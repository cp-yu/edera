from pathlib import Path

from edera_core.config.loader import load_system_config
from edera_core.config.schema import SystemConfig


def test_system_config_default_handlers_dir() -> None:
    assert SystemConfig().handlers_dir == Path("data/handlers")


def test_system_config_explicit_handlers_dir(tmp_path: Path) -> None:
    path = tmp_path / "system.toml"
    path.write_text('handlers_dir = "runtime/handlers"\n', encoding="utf-8")

    assert load_system_config(path).handlers_dir == Path("runtime/handlers")
