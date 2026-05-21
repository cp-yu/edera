from __future__ import annotations

import ast
import importlib.util
import logging
import re
from pathlib import Path

from stockimformation.config.entities import EntityStore


logger = logging.getLogger(__name__)


def evaluate_condition(
    expression: str,
    output: object,
    entity_store: EntityStore | None = None,
    evaluators_dir: Path = Path("config/evaluators"),
) -> bool:
    custom = _custom_evaluator(evaluators_dir)
    context = {"output": output, "entity_store": entity_store}
    if custom is not None:
        try:
            return bool(custom(expression, context))
        except Exception as exc:
            logger.warning("custom condition evaluator failed: %s", exc)
    expression = _rewrite_entity_refs(expression)
    return bool(_eval(ast.parse(expression, mode="eval").body, output, entity_store))


def _custom_evaluator(path: Path):
    file = path / "custom.py"
    if not file.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("stockimformation_custom_evaluator", file)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        logger.warning("failed to load custom condition evaluator: %s", exc)
        return None
    evaluator = getattr(module, "evaluate", None)
    return evaluator if callable(evaluator) else None


def _eval(node: ast.AST, output: object, entity_store: EntityStore | None) -> object:
    if isinstance(node, ast.BoolOp):
        values = [_eval(value, output, entity_store) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval(node.operand, output, entity_store)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, output, entity_store)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval(comparator, output, entity_store)
            if not _compare(op, left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Attribute):
        value = _eval(node.value, output, entity_store)
        return _field(value, node.attr)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id != "entity":
            raise ValueError("unsupported function call")
        if len(node.args) != 2:
            raise ValueError("entity() expects ref and field")
        ref = _eval(node.args[0], output, entity_store)
        field = _eval(node.args[1], output, entity_store)
        if not isinstance(ref, str) or not isinstance(field, str) or entity_store is None:
            return None
        return entity_store.resolve(ref).attributes.get(field)
    if isinstance(node, ast.Name):
        if node.id == "output":
            return output
        raise ValueError(f"unsupported name: {node.id}")
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_eval(item, output, entity_store) for item in node.elts]
    raise ValueError(f"unsupported condition expression: {ast.dump(node)}")


def _rewrite_entity_refs(expression: str) -> str:
    pattern = re.compile(r"entity:([A-Za-z0-9_-]+:[A-Za-z0-9_.-]+)\.([A-Za-z_][A-Za-z0-9_]*)")
    return pattern.sub(lambda match: f"entity('{match.group(1)}', '{match.group(2)}')", expression)


def _field(value: object, name: str) -> object:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _compare(op: ast.cmpop, left: object, right: object) -> bool:
    if isinstance(op, ast.Eq):
        return left == right
    if isinstance(op, ast.NotEq):
        return left != right
    if isinstance(op, ast.Gt):
        return left > right  # type: ignore[operator]
    if isinstance(op, ast.GtE):
        return left >= right  # type: ignore[operator]
    if isinstance(op, ast.Lt):
        return left < right  # type: ignore[operator]
    if isinstance(op, ast.LtE):
        return left <= right  # type: ignore[operator]
    if isinstance(op, ast.In):
        return left in right  # type: ignore[operator]
    raise ValueError(f"unsupported comparison: {type(op).__name__}")
