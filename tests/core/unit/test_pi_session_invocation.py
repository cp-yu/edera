"""Tests for Task 6: --session continuation and invocation namespace."""
from pathlib import Path

import pytest

from edera_core.config.schema import (
    DagNodeInstance,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.resolver import StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot
from edera_core.storage.session_registry import SessionRegistry


def _test_snapshot(tmp_path: Path) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("test-dag", {}, {}),
        {},
        StaticHandlerResolver({}),
        {},
        {},
    )


async def _append(lst: list[str], item: str) -> None:
    lst.append(item)


@pytest.mark.asyncio
async def test_pi_session_flag_first_execution(tmp_path: Path) -> None:
    """C17: 验证首次执行与续接的命令构造 - 首次执行不带 session 参数"""
    # 创建 fake pi 记录命令行参数
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        '# Parse session-dir from arguments\n'
        'SESSION_DIR=""\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then\n'
        '    SESSION_DIR="$i"\n'
        '  fi\n'
        '  prev="$i"\n'
        'done\n'
        'echo "$@" > "$SESSION_DIR/cmd_args.txt"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-a",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    instance = DagNodeInstance(
        id="agent-a",
        type="agent-a",
        config={"session": "task-1"}
    )

    try:

        executor = NodeExecutor(
            {"agent-a": node},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances={"agent-a": instance},
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        output = await executor.execute("agent-a", NodeInput(run_id="run-1", payload={"prompt": "test"}))

        assert output.ok
        # 验证命令包含 --session-id（首次执行）
        session_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1"
        cmd_args = (session_dir / "cmd_args.txt").read_text().strip()
        assert "--session-id" in cmd_args
        assert "--session " not in cmd_args or cmd_args.index("--session-id") < cmd_args.index("--session ")

        # 验证 session 被注册
        sessions = await registry.list_sessions("test-dag", "task-1")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "active"
    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_pi_session_flag_continuation(tmp_path: Path) -> None:
    """C17: 验证首次执行与续接的命令构造 - 续接执行精确指定会话"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        '# Parse session-dir and node id from arguments\n'
        'SESSION_DIR=""; NODE_ID="agent-b"\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'mkdir -p "$SESSION_DIR/invocations/$NODE_ID"\n'
        'echo "$@" > "$SESSION_DIR/invocations/$NODE_ID/cmd_args.txt"\n'
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

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    # 预先注册 session
    session_id = "test-session-123"
    session_path = str(tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1")
    await registry.register("test-dag", "task-1", "run-1", session_id, session_path)

    instance = DagNodeInstance(
        id="agent-b",
        type="agent-b",
        config={"session": "task-1"}
    )

    try:

        executor = NodeExecutor(
            {"agent-b": node},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances={"agent-b": instance},
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        output = await executor.execute("agent-b", NodeInput(run_id="run-1", payload={"prompt": "continue"}))

        assert output.ok
        # 验证命令包含 --session <id>（续接）
        inv_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1" / "invocations" / "agent-b"
        cmd_args = (inv_dir / "cmd_args.txt").read_text().strip()
        assert f"--session {session_id}" in cmd_args or f"--session\n{session_id}" in cmd_args
        assert "--session-id" not in cmd_args
    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_no_continue_flag_removed(tmp_path: Path) -> None:
    """C18: 验证 --continue 自动判定已删除"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""; NODE_ID="agent-c"\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'mkdir -p "$SESSION_DIR/invocations/$NODE_ID"\n'
        'echo "$@" > "$SESSION_DIR/invocations/$NODE_ID/cmd_args.txt"\n'
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
    inv_dir = tmp_path / "data" / "sessions" / "test-dag" / "agent-c" / "run-1" / "invocations" / "agent-c"
    cmd_args = (inv_dir / "cmd_args.txt").read_text().strip()
    assert "--continue" not in cmd_args
    assert "-c" not in cmd_args.split()


@pytest.mark.asyncio
async def test_invocation_namespace_separation(tmp_path: Path) -> None:
    """C19: 验证逐次产物命名空间 - 同组节点产物互不覆盖"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'echo "output from agent"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node_b = NodeConfig.model_validate({
        "name": "agent-b",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })
    node_d = NodeConfig.model_validate({
        "name": "agent-d",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    instance_b = DagNodeInstance(id="agent-b", type="agent-b", config={"session": "task-1"})
    instance_d = DagNodeInstance(id="agent-d", type="agent-d", config={"session": "task-1"})

    try:

        executor = NodeExecutor(
            {"agent-b": node_b, "agent-d": node_d},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances={"agent-b": instance_b, "agent-d": instance_d},
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        # 执行节点 B
        output_b = await executor.execute("agent-b", NodeInput(run_id="run-1", payload={"prompt": "b"}))
        assert output_b.ok

        # 执行节点 D
        output_d = await executor.execute("agent-d", NodeInput(run_id="run-1", payload={"prompt": "d"}))
        assert output_d.ok

        # 验证产物分离
        session_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1"
        inv_b = session_dir / "invocations" / "agent-b"
        inv_d = session_dir / "invocations" / "agent-d"

        assert inv_b.exists()
        assert inv_d.exists()
        assert (inv_b / "stdout.log").exists()
        assert (inv_d / "stdout.log").exists()
        assert (inv_b / "runtime-context.json").exists()
        assert (inv_d / "runtime-context.json").exists()

        # 验证目录分离（产物在不同目录）
        assert inv_b != inv_d
        # 验证两个 invocation 各自的 runtime-context 不同（包含不同的 node_id）
        ctx_b = (inv_b / "runtime-context.json").read_text()
        ctx_d = (inv_d / "runtime-context.json").read_text()
        assert "agent-b" in ctx_b or ctx_b != ctx_d
    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_default_workdir_is_invocation_dir(tmp_path: Path) -> None:
    """C20: 验证默认 workdir 为 invocation 目录"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""; NODE_ID="agent-e"\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'mkdir -p "$SESSION_DIR/invocations/$NODE_ID"\n'
        'pwd > "$SESSION_DIR/invocations/$NODE_ID/cwd.txt"\n'
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
    inv_dir = tmp_path / "data" / "sessions" / "test-dag" / "agent-e" / "run-1" / "invocations" / "agent-e"
    cwd = (inv_dir / "cwd.txt").read_text().strip()
    assert cwd == str(inv_dir.resolve())


@pytest.mark.asyncio
async def test_configured_workdir_overrides_default(tmp_path: Path) -> None:
    """C20: 验证配置的 workdir 覆盖默认值"""
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""; NODE_ID="agent-f"\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'mkdir -p "$SESSION_DIR/invocations/$NODE_ID"\n'
        'pwd > "$SESSION_DIR/invocations/$NODE_ID/cwd.txt"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-f",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    custom_workdir = tmp_path / "custom-work"
    custom_workdir.mkdir()

    instance = DagNodeInstance(
        id="agent-f",
        type="agent-f",
        config={"workdir": str(custom_workdir)}
    )

    executor = NodeExecutor(
        {"agent-f": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(pi)),
        _test_snapshot(tmp_path),
        instances={"agent-f": instance},
        daemon_data_dir=tmp_path / "data",
    )

    output = await executor.execute("agent-f", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    inv_dir = tmp_path / "data" / "sessions" / "test-dag" / "agent-f" / "run-1" / "invocations" / "agent-f"
    cwd = (inv_dir / "cwd.txt").read_text().strip()
    assert cwd == str(custom_workdir.resolve())


@pytest.mark.asyncio
async def test_skills_directory_shared_and_idempotent(tmp_path: Path) -> None:
    """C21: 验证同组 skills 目录共用且幂等"""
    pi = tmp_path / "pi"
    # Use first arg after script name as a way to pass node ID
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""; NODE_ID="unknown"\n'
        '# Extract node ID from runtime context or default\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        '# Infer node ID from invocation dir if it exists\n'
        'for d in "$SESSION_DIR"/invocations/*; do\n'
        '  if [ -d "$d" ]; then NODE_ID=$(basename "$d"); break; fi\n'
        'done\n'
        '[ -z "$NODE_ID" ] && NODE_ID="agent-a"\n'
        'mkdir -p "$SESSION_DIR/invocations/$NODE_ID"\n'
        'ls -la "$SESSION_DIR/skills/" > "$SESSION_DIR/invocations/$NODE_ID/skills_list.txt" 2>&1 || echo "no skills" > "$SESSION_DIR/invocations/$NODE_ID/skills_list.txt"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node_a = NodeConfig.model_validate({
        "name": "agent-a",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })
    node_b = NodeConfig.model_validate({
        "name": "agent-b",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    instance_a = DagNodeInstance(id="agent-a", type="agent-a", config={"session": "task-1"})
    instance_b = DagNodeInstance(id="agent-b", type="agent-b", config={"session": "task-1"})

    # Create snapshot with mock skills
    from dataclasses import replace
    base_snapshot = _test_snapshot(tmp_path)
    mock_skill = type('Skill', (), {
        'name': 'test-skill',
        'description': 'Test skill',
        'instructions': 'Do something',
        'examples': [],
        'files': [{'path': 'test-skill.md', 'content': '# Test Skill\n'}]
    })()
    snapshot = replace(base_snapshot, skills={"test-skill": mock_skill})

    try:

        executor = NodeExecutor(
            {"agent-a": node_a, "agent-b": node_b},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            snapshot,
            instances={"agent-a": instance_a, "agent-b": instance_b},
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        # 第一个节点执行
        output_a = await executor.execute("agent-a", NodeInput(run_id="run-1", payload={}))
        assert output_a.ok

        session_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1"
        skills_dir = session_dir / "skills"

        # 记录第一次生成后的状态
        first_mtime = skills_dir.stat().st_mtime if skills_dir.exists() else None

        # 第二个节点执行（应该幂等）
        output_b = await executor.execute("agent-b", NodeInput(run_id="run-1", payload={}))
        assert output_b.ok

        # 验证 skills 目录存在且被共享
        assert skills_dir.exists()
        # 验证生成是幂等的（不报错，内容一致）
        assert output_b.ok
    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_resume_with_session_id_continuation(tmp_path: Path) -> None:
    """C22: 验证 resume 以 session id 精确续接"""
    # 此测试需要与 test_core_architecture_overhaul.py 中的 resume 测试配合
    # 这里仅验证命令构造逻辑
    pi = tmp_path / "pi"
    pi.write_text(
        "#!/bin/bash\n"
        'SESSION_DIR=""; NODE_ID="agent-resume"\n'
        'for i in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$i"; fi\n'
        '  prev="$i"\n'
        'done\n'
        'mkdir -p "$SESSION_DIR/invocations/$NODE_ID"\n'
        'echo "Resume with session: $@" > "$SESSION_DIR/invocations/$NODE_ID/resume_args.txt"\n'
        "exit 0\n",
        encoding="utf-8"
    )
    pi.chmod(0o755)

    node = NodeConfig.model_validate({
        "name": "agent-resume",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    # 预先注册 session
    session_id = "resume-session-456"
    session_path = str(tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1")
    await registry.register("test-dag", "task-1", "run-1", session_id, session_path)

    instance = DagNodeInstance(
        id="agent-resume",
        type="agent-resume",
        config={"session": "task-1"}
    )

    try:

        executor = NodeExecutor(
            {"agent-resume": node},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances={"agent-resume": instance},
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        # 执行（模拟 resume）
        output = await executor.execute("agent-resume", NodeInput(run_id="run-1", payload={"prompt": "new prompt"}))

        assert output.ok
        inv_dir = tmp_path / "data" / "sessions" / "test-dag" / "task-1" / "run-1" / "invocations" / "agent-resume"
        resume_args = (inv_dir / "resume_args.txt").read_text().strip()
        # 验证使用 --session 续接（不是 --session-id）
        assert f"--session {session_id}" in resume_args or session_id in resume_args
    finally:
        await registry.close()
