from __future__ import annotations

from collections.abc import Sequence

from edera_core.node.models import NodeOutput


def collect(values: Sequence[object]) -> list[object]:
    collected: list[object] = []
    for value in values:
        if isinstance(value, list):
            collected.extend(value)
        else:
            collected.append(value)
    return collected


def _failure_kind(output: NodeOutput) -> str | None:
    value = output.metadata.get("failure_kind")
    if isinstance(value, str):
        return value
    return None if output.ok else "execution_failed"


def _node_run_metadata(output: NodeOutput) -> dict[str, object] | None:
    keys = ("parent_run_id", "sub_dag_run_id", "parent_node")
    metadata = {key: output.metadata[key] for key in keys if key in output.metadata}
    return metadata or None


def _mapped_input(payload: object, input_mapping: dict[str, str] | str) -> object:
    if not input_mapping:
        return payload
    if isinstance(input_mapping, str):
        return _path_value(payload, input_mapping, _MISSING)
    return {name: value for name, path in input_mapping.items() if (value := _path_value(payload, path, _MISSING)) is not _MISSING}


_MISSING = object()


def _path_value(payload: object, path: str, default: object) -> object:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return default
    return current


def _input_mapping_ref(ref: str) -> str:
    if ref.startswith("entity://"):
        name = ref.removeprefix("entity://")
        return f"input_mapping:{name}"
    return ref


def _str_mapping(value: object) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}


def _node_input_mappings(value: object) -> dict[str, dict[str, str] | str]:
    if not isinstance(value, dict):
        return {}
    mappings: dict[str, dict[str, str] | str] = {}
    for node, mapping in value.items():
        mappings[str(node)] = mapping if isinstance(mapping, str) else _str_mapping(mapping)
    return mappings


def _str_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _merge_stream_results(node: str, results: list[NodeOutput]) -> NodeOutput:
    payload = [result.payload for result in results if result.ok]
    failures = {f"{node}:stream:{index}": result.error or "node failed" for index, result in enumerate(results) if not result.ok}
    return NodeOutput(
        node_name=node,
        ok=bool(payload),
        payload=payload,
        metadata={"stream_failures": failures},
        error=None if payload else "; ".join(failures.values()) or "stream produced no output",
    )


def _merge_fan_out_results(node: str, results: list[NodeOutput]) -> NodeOutput:
    payload = [result.payload for result in results if result.ok]
    failures = {f"{node}:fanout:{index}": result.error or "node failed" for index, result in enumerate(results) if not result.ok}
    return NodeOutput(
        node_name=node,
        ok=bool(payload),
        payload=payload,
        metadata={"fan_out_failures": failures},
        error=None if payload else "; ".join(failures.values()) or "fan_out produced no output",
    )
