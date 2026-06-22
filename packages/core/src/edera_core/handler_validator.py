from __future__ import annotations

import ast
from pathlib import Path


def validate_handler(path: Path) -> list[str]:
    errors: list[str] = []
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg}"]
    fn = _find_function(tree, "run")
    if fn is None:
        return ["missing async def run"]
    if not isinstance(fn, ast.AsyncFunctionDef):
        errors.append("run must be async def")
    a = fn.args
    if (
        len(a.args) + len(a.posonlyargs) != 1
        or a.vararg is not None
        or a.kwarg is not None
        or len(a.kwonlyargs) != 0
    ):
        errors.append("run must accept exactly 1 parameter")
    return errors


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None
