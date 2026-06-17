from pathlib import Path

from edera_core.config.schema import SystemConfig


def test_skills_dir_default() -> None:
    config = SystemConfig()

    assert config.skills_dir == Path("data/skills")


def test_skills_dir_overridable_by_toml() -> None:
    import tomllib

    raw = tomllib.loads('skills_dir = "custom/skills"')
    config = SystemConfig.model_validate(raw)

    assert config.skills_dir == Path("custom/skills")


def test_startup_window_seconds_default_10() -> None:
    config = SystemConfig()

    assert config.startup_window_seconds == 10


def test_startup_window_seconds_custom_value() -> None:
    import tomllib

    raw = tomllib.loads("startup_window_seconds = 1")
    config = SystemConfig.model_validate(raw)

    assert config.startup_window_seconds == 1

