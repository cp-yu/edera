from __future__ import annotations

import inspect
from pathlib import Path


def validate_handler(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg}"]
    namespace: dict[str, object] = {}
    try:
        exec(code, namespace)
    except Exception as exc:
        return [f"load error: {exc}"]
    run = namespace.get("run")
    if not callable(run):
        return ["missing callable run"]
    count = len(inspect.signature(run).parameters)
    if count not in {1, 3}:
        errors.append("run must accept 1 or 3 parameters")
    return errors
