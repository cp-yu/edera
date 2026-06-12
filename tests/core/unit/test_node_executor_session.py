"""C12-C16: Executor 集成 session 解析测试"""
import pytest
from pathlib import Path

from edera_core.config.schema import (
    DagNodeInstance,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.snapshot import DagExecutionSnapshot, DagExecutionClosure
from edera_core.resolver import StaticHandlerResolver
from edera_core.storage.session_registry import SessionRegistry


def _test_snapshot(tmp_path: Path) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("test-dag", {}, {}),
        {},
        StaticHandlerResolver({}),
        {},
        {},
    )


@pytest.mark.asyncio
async def test_session_group_path_resolution(tmp_path: Path):
    """C12: 验证组名解析为组路径"""
    registry = SessionRegistry(":memory:")
    await registry.initialize()

    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\necho 'session-123' > session-123.jsonl\necho 'ok'\n", encoding="utf-8")
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-node",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    instance = DagNodeInstance(
        id="node-B",
        type="agent-node",
        config={"session": "task-1"}
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        instances={instance.id: instance},
        daemon_data_dir=tmp_path / "data",
        session_registry=registry,
    )

    output = await executor.execute(instance.id, NodeInput(run_id="run-001", payload={}))

    assert output.ok
    # 验证 session 目录为 {dag}/task-1/{run_id}
    session_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-001"
    assert session_dir.exists()
    # 验证 invocation 目录
    inv_dir = session_dir / "invocations" / "node-B"
    assert inv_dir.exists()
    assert (inv_dir / "stdout.log").exists()


@pytest.mark.asyncio
async def test_no_session_uses_instance_id(tmp_path: Path):
    """C14: 验证未声明 session 行为不变"""
    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\necho 'ok'\n", encoding="utf-8")
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-node",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-node", NodeInput(run_id="run-001", payload={}))

    assert output.ok
    # 验证使用 instance_id 作为路径
    session_dir = tmp_path / "data" / "sessions" / "test-dag" / "agent-node" / "run-001"
    assert session_dir.exists()


@pytest.mark.asyncio
async def test_cross_dag_latest_resolution(tmp_path: Path):
    """C15: 验证跨 DAG 引用经注册表解析"""
    registry = SessionRegistry(":memory:")
    await registry.initialize()

    # 预先登记一个 completed session
    await registry.register("relay-main", "task-1", "run-source", "session-src", str(tmp_path / "source"))
    await registry.finish("relay-main", "task-1", "run-source", "completed")

    # 创建源 session 目录和文件
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "session-src.jsonl").write_text("[]", encoding="utf-8")

    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\necho 'continued'\n", encoding="utf-8")
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-node",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    instance = DagNodeInstance(
        id="node-X",
        type="agent-node",
        config={"session": "relay-main/task-1@latest"}
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        instances={instance.id: instance},
        daemon_data_dir=tmp_path / "data",
        session_registry=registry,
    )

    output = await executor.execute(instance.id, NodeInput(run_id="run-consumer", payload={}))

    assert output.ok
    assert output.metadata["session_id"] == "session-src"


@pytest.mark.asyncio
async def test_workdir_defaults_to_invocation_dir(tmp_path: Path):
    """C20: 验证默认 workdir 为 invocation 目录"""
    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\npwd\n", encoding="utf-8")
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-node",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    instance = DagNodeInstance(
        id="node-B",
        type="agent-node",
        config={"session": "task-1"}
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        instances={instance.id: instance},
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute(instance.id, NodeInput(run_id="run-001", payload={}))

    assert output.ok
    # 验证 cwd 为 invocation 目录
    expected_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-001" / "invocations" / "node-B"
    assert output.payload["stdout"].strip() == str(expected_dir)
