from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path


def test_extension_handlers_use_single_context_parameter() -> None:
    sys.path.insert(0, "extensions")
    for name in [
        "rss-fetcher",
        "web-scraper",
        "api-fetcher",
        "reader",
        "advisor",
        "briefing-generator",
        "notifier",
    ]:
        spec = importlib.util.spec_from_file_location(name, Path("extensions") / name / "handler.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert len(inspect.signature(module.run).parameters) == 1
