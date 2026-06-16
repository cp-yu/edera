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
