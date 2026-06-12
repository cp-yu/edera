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


@pytest.mark.asyncio
async def test_pi_session_flag_first_execution(tmp_path: Path):
    """C17: 首次执行使用 --session-id 创建新会话"""
    import json as _json

    capture = tmp_path / "args.json"
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('ok')\n",
        encoding="utf-8",
    )
    pi.chmod(0o755)

    registry = SessionRegistry(":memory:")
    await registry.initialize()

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
        config={"session": "task-1"},
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

    output = await executor.execute(instance.id, NodeInput(run_id="run-1", payload={}))

    assert output.ok
    args = _json.loads(capture.read_text())
    # 首次执行：应包含 --session-id（预生成），不含 --session
    assert "--session-id" in args
    assert "--session" not in args or args.index("--session-id") < args.index("--session")
    session_id_val = args[args.index("--session-id") + 1]
    assert len(session_id_val) == 32  # uuid4().hex


@pytest.mark.asyncio
async def test_pi_session_flag_continuation(tmp_path: Path):
    """C17: 续接执行使用 --session 精确续接已登记会话"""
    import json as _json

    capture = tmp_path / "args.json"
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('ok')\n",
        encoding="utf-8",
    )
    pi.chmod(0o755)

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    # 预先登记 session_id（模拟组内首节点已执行）
    await registry.register("test-dag", "task-1", "run-1", "existing-session-abc", str(tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1"))

    node = NodeConfig.model_validate({
        "name": "agent-node",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })
    instance = DagNodeInstance(
        id="node-D",
        type="agent-node",
        config={"session": "task-1"},
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

    output = await executor.execute(instance.id, NodeInput(run_id="run-1", payload={}))

    assert output.ok
    args = _json.loads(capture.read_text())
    # 续接执行：应包含 --session <existing_id>，不含 --session-id
    assert "--session" in args
    assert "--session-id" not in args
    session_val = args[args.index("--session") + 1]
    assert session_val == "existing-session-abc"


@pytest.mark.asyncio
async def test_invocation_namespace(tmp_path: Path):
    """C19: 验证逐次产物写入节点专属目录，同组节点产物互不覆盖"""
    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\necho 'node output'\n", encoding="utf-8")
    pi.chmod(0o755)

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    node = NodeConfig.model_validate({
        "name": "agent-node",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    instance_b = DagNodeInstance(id="node-B", type="agent-node", config={"session": "task-1"})
    instance_d = DagNodeInstance(id="node-D", type="agent-node", config={"session": "task-1"})

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        instances={instance_b.id: instance_b, instance_d.id: instance_d},
        daemon_data_dir=tmp_path / "data",
        session_registry=registry,
    )

    # 执行同组两个节点
    output_b = await executor.execute(instance_b.id, NodeInput(run_id="run-1", payload={}))
    output_d = await executor.execute(instance_d.id, NodeInput(run_id="run-1", payload={}))

    assert output_b.ok
    assert output_d.ok

    # 验证产物分别位于 invocations/B 和 invocations/D
    session_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1"
    inv_b = session_dir / "invocations" / "node-B"
    inv_d = session_dir / "invocations" / "node-D"

    assert (inv_b / "stdout.log").exists()
    assert (inv_b / "runtime-context.json").exists()
    assert (inv_d / "stdout.log").exists()
    assert (inv_d / "runtime-context.json").exists()

    # 验证产物互不覆盖
    assert (inv_b / "stdout.log").read_text() == "node output\n"
    assert (inv_d / "stdout.log").read_text() == "node output\n"


@pytest.mark.asyncio
async def test_workdir_configured(tmp_path: Path):
    """C20: 验证配置 workdir 时使用配置值"""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

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
        config={"session": "task-1", "workdir": str(project_dir)},
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        instances={instance.id: instance},
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute(instance.id, NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload["stdout"].strip() == str(project_dir)


@pytest.mark.asyncio
async def test_skills_idempotent(tmp_path: Path):
    """C21: 验证同组 skills 目录共用且重复生成幂等"""
    from edera_core.config.schema import DagConfig

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

    instance_b = DagNodeInstance(id="node-B", type="agent-node", config={"session": "task-1"})
    instance_d = DagNodeInstance(id="node-D", type="agent-node", config={"session": "task-1"})

    # 创建带 skills 的 snapshot
    from edera_core.snapshot import DagExecutionSnapshot, DagExecutionClosure
    from edera_core.resolver import StaticHandlerResolver
    from edera_core.config.schema import SkillConfig

    skill = SkillConfig(
        name="test-skill",
        files=[
            {"path": "SKILL.md", "content": "# Test Skill"},
            {"path": "prompts/main.txt", "content": "test prompt"},
        ],
    )

    snapshot = DagExecutionSnapshot(
        DagExecutionClosure("test-dag", {}, {}),
        {},  # entity_types
        StaticHandlerResolver({}),
        {},  # extension_table_names
        {"test-skill": skill},  # skills
    )

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        snapshot,
        instances={instance_b.id: instance_b, instance_d.id: instance_d},
        daemon_data_dir=tmp_path / "data",
    )

    # 执行第一个节点
    output_b = await executor.execute(instance_b.id, NodeInput(run_id="run-1", payload={}))
    assert output_b.ok

    session_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1"
    skill_file = session_dir / "skills" / "test-skill" / "SKILL.md"
    prompt_file = session_dir / "skills" / "test-skill" / "prompts" / "main.txt"

    assert skill_file.exists()
    assert prompt_file.exists()
    first_content = skill_file.read_text()

    # 执行第二个节点，验证 skills 重复生成幂等
    output_d = await executor.execute(instance_d.id, NodeInput(run_id="run-1", payload={}))
    assert output_d.ok

    # 验证内容一致且不报错
    assert skill_file.read_text() == first_content
    assert prompt_file.read_text() == "test prompt"
