from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path


def test_extension_handlers_use_single_context_parameter() -> None:
    original_path = list(sys.path)
    original_modules = {name: module for name, module in sys.modules.items() if name == "_lib" or name.startswith("_lib.")}
    sys.path = ["extensions", *[path for path in sys.path if path != "extensions"]]
    for name in original_modules:
        sys.modules.pop(name, None)
    try:
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
    finally:
        sys.path = original_path
        for name in list(sys.modules):
            if name == "_lib" or name.startswith("_lib."):
                sys.modules.pop(name, None)
        sys.modules.update(original_modules)
