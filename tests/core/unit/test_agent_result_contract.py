"""Tests for Task 7: Agent 结构化输出契约."""
from pathlib import Path

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import (
    DagNodeInstance,
    EntitiesConfig,
    EntityTypeConfig,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.resolver import StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot


def _test_snapshot(tmp_path: Path, entity_store: EntityStore | None = None) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("test-dag", {}, {}),
        {},
        StaticHandlerResolver({}),
        {},
        {},
    )


@pytest.mark.asyncio
async def test_result_file_validation_passes(tmp_path: Path) -> None:
    """C23: 验证结果文件校验通过路径"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'RESULT_PATH="$SESSION_DIR/invocations/agent-a/result.json"\n'
        'echo \'{"answer": "test result", "count": 42}\' > "$RESULT_PATH"\n'
        'echo "Processing complete"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    # 创建带 schema 的 entity type
    entity_types = {
        "TestOutput": EntityTypeConfig(
            display_name="Test Output",
            business_id_field="answer",
            display_template="{answer}",
            schema={
                "type": "object",
                "required": ["answer", "count"],
                "properties": {
                    "answer": {"type": "string"},
                    "count": {"type": "number"}
                }
            }
        )
    }
    entity_store = EntityStore(
        EntitiesConfig(entities=[]),
        entity_types,
        {}
    )

    node = NodeConfig.model_validate({
        "name": "agent-a",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "TestOutput",
    })

    executor = NodeExecutor(
        {"agent-a": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path, entity_store),
        entity_store=entity_store,
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-a", NodeInput(run_id="run-1", payload={"prompt": "test"}))

    assert output.ok
    assert output.payload == {"answer": "test result", "count": 42}
    assert "result_degraded" not in output.metadata


@pytest.mark.asyncio
async def test_result_file_without_schema_accepts_any_json(tmp_path: Path) -> None:
    """C23: 无 schema 时自由 JSON"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'RESULT_PATH="$SESSION_DIR/invocations/agent-b/result.json"\n'
        'echo \'{"any": "structure", "is": ["valid"]}\' > "$RESULT_PATH"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-b",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    executor = NodeExecutor(
        {"agent-b": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-b", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload == {"any": "structure", "is": ["valid"]}
    assert "result_degraded" not in output.metadata


@pytest.mark.asyncio
async def test_result_file_missing_degrades_to_stdout(tmp_path: Path) -> None:
    """C24: 验证结果文件缺失降级"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'echo "Output without result file"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-c",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    executor = NodeExecutor(
        {"agent-c": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-c", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload == {"stdout": "Output without result file"}
    assert output.metadata.get("result_degraded") is True


@pytest.mark.asyncio
async def test_result_file_schema_validation_failure_degrades(tmp_path: Path) -> None:
    """C24: 验证校验失败降级"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'RESULT_PATH="$SESSION_DIR/invocations/agent-d/result.json"\n'
        '# 写入不符合 schema 的 JSON（缺少 required 字段）\n'
        'echo \'{"wrong": "structure"}\' > "$RESULT_PATH"\n'
        'echo "Result written but invalid"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    entity_types = {
        "StrictOutput": EntityTypeConfig(
            display_name="Strict Output",
            business_id_field="required_field",
            display_template="{required_field}",
            schema={
                "type": "object",
                "required": ["required_field"],
                "properties": {
                    "required_field": {"type": "string"}
                }
            }
        )
    }
    entity_store = EntityStore(
        EntitiesConfig(entities=[]),
        entity_types,
        {}
    )

    node = NodeConfig.model_validate({
        "name": "agent-d",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "StrictOutput",
    })

    executor = NodeExecutor(
        {"agent-d": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path, entity_store),
        entity_store=entity_store,
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-d", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload == {"stdout": "Result written but invalid"}
    assert output.metadata.get("result_degraded") is True


@pytest.mark.asyncio
async def test_result_file_invalid_json_degrades(tmp_path: Path) -> None:
    """C24: 验证 JSON 解析失败降级"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'RESULT_PATH="$SESSION_DIR/invocations/agent-e/result.json"\n'
        'echo "not valid json" > "$RESULT_PATH"\n'
        'echo "Wrote invalid JSON"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-e",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    executor = NodeExecutor(
        {"agent-e": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-e", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload == {"stdout": "Wrote invalid JSON"}
    assert output.metadata.get("result_degraded") is True
