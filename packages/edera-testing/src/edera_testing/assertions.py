from __future__ import annotations

import inspect
from pathlib import Path

import yaml


def assert_handler_signature(module: object) -> None:
    run = getattr(module, "run", None)
    assert run is not None, "handler module must define run"
    assert len(inspect.signature(run).parameters) == 1, "run must accept exactly one parameter"


def assert_manifest_valid(manifest_path: str | Path) -> None:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict), "manifest must be a mapping"
    missing = {"name", "version", "handlers"} - set(data)
    assert not missing, f"manifest missing required fields: {', '.join(sorted(missing))}"
