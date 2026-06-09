from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from edera_testing import assert_handler_signature


def test_extension_handlers_use_single_context_parameter() -> None:
    original_path = list(sys.path)
    original_modules = {name: module for name, module in sys.modules.items() if name == "_lib" or name.startswith("_lib.")}
    root = Path(__file__).parents[1]
    lib_root = root / "_lib" / "common"
    sys.path = [
        str(root),
        str(lib_root),
        *[path for path in sys.path if path not in {str(root), str(lib_root)}],
    ]
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
            path = root / "_providers" / name / "handler.py"
            spec = importlib.util.spec_from_file_location(name, path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert_handler_signature(module)
    finally:
        sys.path = original_path
        for name in list(sys.modules):
            if name == "_lib" or name.startswith("_lib."):
                sys.modules.pop(name, None)
        sys.modules.update(original_modules)
