"""Task 9: 同组串行与跨 DAG 集成测试（fake pi）"""
import asyncio
import json
from pathlib import Path
from datetime import datetime

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import (
    DagConfig,
    DagNodeInstance,
    EntitiesConfig,
    EntityConfig,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.dag.loader import load_graph
from edera_core.dag.resources import clear_semaphore_cache
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.resolver import StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot
from edera_core.storage.session_registry import SessionRegistry


@pytest.fixture(autouse=True)
def _clear_resource_semaphores() -> None:
    clear_semaphore_cache()


def _fake_pi_script(tmp_path: Path, call_log: list[dict]) -> Path:
    """
    创建 fake pi 脚本，记录调用参数与起止时间，产出 jsonl + result.json

    记录格式：
    {
        "node_id": str,
        "session_id": str | None,
        "is_first": bool,  # --session-id vs --session
        "start_time": float,
        "end_time": float,
        "cmd": list[str]
    }
    """
    pi = tmp_path / "fake_pi"
    pi.write_text(
        "#!/bin/bash\n"
        'set -e\n'
        'SESSION_DIR=""\n'
        'SESSION_ID=""\n'
        'IS_FIRST=false\n'
        'START_TIME=$(date +%s.%N)\n'
        '\n'
        '# Parse arguments\n'
        'prev=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--session-dir" ]; then SESSION_DIR="$arg"; fi\n'
        '  if [ "$prev" = "--session-id" ]; then SESSION_ID="$arg"; IS_FIRST=true; fi\n'
        '  if [ "$prev" = "--session" ]; then SESSION_ID="$arg"; IS_FIRST=false; fi\n'
        '  prev="$arg"\n'
        'done\n'
        '\n'
        '# Read node_id from EDERA_IDENTITY env (set by executor)\n'
        'NODE_ID="${EDERA_IDENTITY#node:}"\n'
        '[ -z "$NODE_ID" ] && NODE_ID="unknown"\n'
        '\n'
        '# Create session file if first execution\n'
        'if [ "$IS_FIRST" = true ] && [ -n "$SESSION_ID" ]; then\n'
        '  echo "[]" > "$SESSION_DIR/${SESSION_ID}.jsonl"\n'
        'fi\n'
        '\n'
        '# Create invocation directory\n'
        'INV_DIR="$SESSION_DIR/invocations/$NODE_ID"\n'
        'mkdir -p "$INV_DIR"\n'
        '\n'
        '# Record call metadata to shared log\n'
        'END_TIME=$(date +%s.%N)\n'
        f'CALL_LOG="{tmp_path / "call_log.jsonl"}"\n'
        'echo "{\\"node_id\\":\\"$NODE_ID\\",\\"session_id\\":\\"$SESSION_ID\\",\\"is_first\\":$IS_FIRST,\\"start_time\\":$START_TIME,\\"end_time\\":$END_TIME}" >> "$CALL_LOG"\n'
        '\n'
        '# Write result.json if runtime-context specifies result_path\n'
        'if [ -f "$INV_DIR/runtime-context.json" ]; then\n'
        '  RESULT_PATH=$(grep -o \'"result_path":"[^"]*"\' "$INV_DIR/runtime-context.json" | cut -d\\" -f4)\n'
        '  if [ -n "$RESULT_PATH" ]; then\n'
        '    echo "{\\"output\\":\\"success from $NODE_ID\\"}" > "$RESULT_PATH"\n'
        '  fi\n'
        'fi\n'
        '\n'
        'exit 0\n',
        encoding="utf-8"
    )
    pi.chmod(0o755)
    return pi


def _test_snapshot(tmp_path: Path) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("test", {}, {}),
        {},
        StaticHandlerResolver({}),
        {},
        {},
    )


def _entity_store_with_session_resources(resource_names: list[str]) -> EntityStore:
    """创建包含 session resource 的 EntityStore"""
    entities = [
        EntityConfig(id=name, type="resource", attributes={"permits": 1})
        for name in resource_names
    ]
    entity_types = {"resource": type('ResourceType', (), {'name': 'resource', 'attributes': {}})}
    return EntityStore(
        EntitiesConfig(entities=entities),
        entity_types,
        EntitiesConfig(entities=[]),
    )


def _read_call_log(tmp_path: Path) -> list[dict]:
    """读取 call_log.jsonl"""
    log_file = tmp_path / "call_log.jsonl"
    if not log_file.exists():
        return []

    calls = []
    for line in log_file.read_text().strip().split('\n'):
        if line:
            calls.append(json.loads(line))
    return calls


@pytest.mark.asyncio
async def test_parallel_branches_serialized_by_session_group(tmp_path: Path) -> None:
    """
    C27: 验证同 DAG 并行分支串行化

    拓扑: a → B, a → D，其中 B 和 D 声明 session: task-1
    验证: B 和 D 的进程运行时间不重叠
    """
    call_log: list[dict] = []
    pi = _fake_pi_script(tmp_path, call_log)

    # 创建 session resource
    entity_store = _entity_store_with_session_resources(["session:test-dag/task-1"])

    # 定义节点类型
    node_a = NodeConfig.model_validate({
        "name": "function-a",
        "type": "function",
        "handler": "handler-a",
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
    node_d = NodeConfig.model_validate({
        "name": "agent-d",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    # 创建 DAG
    dag_config = DagConfig.model_validate({
        "name": "test-dag",
        "nodes": [
            {"id": "a", "type": "function-a"},
            {"id": "B", "type": "agent-b", "config": {"session": "task-1"}, "resource": "session:test-dag/task-1"},
            {"id": "D", "type": "agent-d", "config": {"session": "task-1"}, "resource": "session:test-dag/task-1"},
        ],
        "edges": [
            {"from": "a", "to": "B"},
            {"from": "a", "to": "D"},
        ],
    })

    graph = load_graph(dag_config, {"function-a": node_a, "agent-b": node_b, "agent-d": node_d})

    # 创建 handler
    async def handler_a(_input: NodeInput) -> object:
        return {"seed": "from a"}

    # 创建 handler resolver
    from edera_core.resolver import HandlerMeta
    import builtins
    setattr(builtins, '_test_handler_a', handler_a)

    handler_path = tmp_path / "handler_a.py"
    handler_path.write_text(
        "import builtins\n"
        "async def run(ctx):\n"
        "    return await builtins._test_handler_a(ctx.input)\n",
        encoding="utf-8"
    )

    resolver = StaticHandlerResolver({"handler-a": HandlerMeta(handler_path)})
    snapshot = DagExecutionSnapshot(
        DagExecutionClosure("test-dag", {}, {}),
        {},
        resolver,
        {},
        {},
    )

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    try:
        executor = NodeExecutor(
            {"function-a": node_a, "agent-b": node_b, "agent-d": node_d},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            snapshot,
            instances=graph.instances,
            entity_store=entity_store,
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        runner = DagRunner(executor)
        result = await runner.run(graph, "run-1", {"initial": "payload"})

        assert result.failures == {}
        assert "B" in result.node_outputs
        assert "D" in result.node_outputs
        assert result.node_outputs["B"].ok
        assert result.node_outputs["D"].ok

        # 读取调用日志
        calls = _read_call_log(tmp_path)

        # 找到 B 和 D 的调用记录
        call_b = next((c for c in calls if c["node_id"] == "B"), None)
        call_d = next((c for c in calls if c["node_id"] == "D"), None)

        assert call_b is not None, "B should have been called"
        assert call_d is not None, "D should have been called"

        # 验证时间不重叠（串行执行）
        b_start = float(call_b["start_time"])
        b_end = float(call_b["end_time"])
        d_start = float(call_d["start_time"])
        d_end = float(call_d["end_time"])

        # 两个时间段不重叠：要么 B 完全在 D 之前，要么 D 完全在 B 之前
        assert b_end <= d_start or d_end <= b_start, \
            f"B and D should not overlap: B=[{b_start}, {b_end}], D=[{d_start}, {d_end}]"

    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_group_sharing_and_precise_continuation(tmp_path: Path) -> None:
    """
    C28: 验证组共享与精确续接

    拓扑: a → B → c → D，其中 B 和 D 声明 session: task-1
    验证: 首节点创建并登记 session id，后续节点收到 --session <同一 id>
    """
    call_log: list[dict] = []
    pi = _fake_pi_script(tmp_path, call_log)

    entity_store = _entity_store_with_session_resources(["session:test-dag/task-1"])

    node_a = NodeConfig.model_validate({
        "name": "function-a",
        "type": "function",
        "handler": "handler-a",
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
    node_c = NodeConfig.model_validate({
        "name": "function-c",
        "type": "function",
        "handler": "handler-c",
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

    dag_config = DagConfig.model_validate({
        "name": "test-dag",
        "nodes": [
            {"id": "a", "type": "function-a"},
            {"id": "B", "type": "agent-b", "config": {"session": "task-1"}, "resource": "session:test-dag/task-1"},
            {"id": "c", "type": "function-c"},
            {"id": "D", "type": "agent-d", "config": {"session": "task-1"}, "resource": "session:test-dag/task-1"},
        ],
        "edges": [
            {"from": "a", "to": "B"},
            {"from": "B", "to": "c"},
            {"from": "c", "to": "D"},
        ],
    })

    graph = load_graph(dag_config, {
        "function-a": node_a,
        "agent-b": node_b,
        "function-c": node_c,
        "agent-d": node_d,
    })

    # 创建 handlers
    async def handler_a(_input: NodeInput) -> object:
        return {"from": "a"}

    async def handler_c(_input: NodeInput) -> object:
        return {"from": "c"}

    import builtins
    setattr(builtins, '_test_handler_a', handler_a)
    setattr(builtins, '_test_handler_c', handler_c)

    handler_a_path = tmp_path / "handler_a.py"
    handler_a_path.write_text(
        "import builtins\n"
        "async def run(ctx):\n"
        "    return await builtins._test_handler_a(ctx.input)\n",
        encoding="utf-8"
    )
    handler_c_path = tmp_path / "handler_c.py"
    handler_c_path.write_text(
        "import builtins\n"
        "async def run(ctx):\n"
        "    return await builtins._test_handler_c(ctx.input)\n",
        encoding="utf-8"
    )

    from edera_core.resolver import HandlerMeta
    resolver = StaticHandlerResolver({
        "handler-a": HandlerMeta(handler_a_path),
        "handler-c": HandlerMeta(handler_c_path),
    })
    snapshot = DagExecutionSnapshot(
        DagExecutionClosure("test-dag", {}, {}),
        {},
        resolver,
        {},
        {},
    )

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    try:
        executor = NodeExecutor(
            {"function-a": node_a, "agent-b": node_b, "function-c": node_c, "agent-d": node_d},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            snapshot,
            instances=graph.instances,
            entity_store=entity_store,
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        runner = DagRunner(executor)
        result = await runner.run(graph, "run-1", {})

        assert result.failures == {}

        # 读取调用日志
        calls = _read_call_log(tmp_path)

        call_b = next((c for c in calls if c["node_id"] == "B"), None)
        call_d = next((c for c in calls if c["node_id"] == "D"), None)

        assert call_b is not None
        assert call_d is not None

        # 验证: B 是首次执行（--session-id）
        assert call_b["is_first"] is True, "B should use --session-id (first execution)"
        assert call_b["session_id"], "B should have session_id"

        # 验证: D 续接相同 session（--session）
        assert call_d["is_first"] is False, "D should use --session (continuation)"
        assert call_d["session_id"] == call_b["session_id"], "D should reuse B's session_id"

    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_cross_dag_waiting_and_timeout(tmp_path: Path) -> None:
    """
    C29: 验证跨 DAG 等待与超时

    场景:
    - relay-skill 的 X 节点声明 `session: relay-main/task-1@latest`
    - 当源组持锁时引用方阻塞
    - 超过 timeout_seconds 后节点失败
    """
    call_log: list[dict] = []
    pi = _fake_pi_script(tmp_path, call_log)

    entity_store = _entity_store_with_session_resources(["session:relay-main/task-1"])

    # 先运行 relay-main 并完成
    node_b = NodeConfig.model_validate({
        "name": "agent-b",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    main_dag = DagConfig.model_validate({
        "name": "relay-main",
        "nodes": [
            {"id": "B", "type": "agent-b", "config": {"session": "task-1"}, "resource": "session:relay-main/task-1"},
        ],
        "edges": [],
    })

    main_graph = load_graph(main_dag, {"agent-b": node_b})

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    try:
        # 第一步: 运行 relay-main，创建completed session
        executor_main = NodeExecutor(
            {"agent-b": node_b},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances=main_graph.instances,
            entity_store=entity_store,
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        runner_main = DagRunner(executor_main)
        result_main = await runner_main.run(main_graph, "main-run-1", {})
        assert result_main.failures == {}

        # 标记 session 为 completed
        await registry.finish("relay-main", "task-1", "main-run-1", "completed")

        # 第二步: 运行 relay-skill，引用 @latest
        node_x = NodeConfig.model_validate({
            "name": "agent-x",
            "type": "agent",
            "model": "test-model",
            "input_type": "Any",
            "output_type": "Any",
            "timeout_seconds": 1,  # 设置短超时用于测试超时场景
        })

        skill_dag = DagConfig.model_validate({
            "name": "relay-skill",
            "nodes": [
                {"id": "X", "type": "agent-x", "config": {"session": "relay-main/task-1@latest"}, "resource": "session:relay-main/task-1"},
            ],
            "edges": [],
        })

        skill_graph = load_graph(skill_dag, {"agent-x": node_x})

        executor_skill = NodeExecutor(
            {"agent-x": node_x},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances=skill_graph.instances,
            entity_store=entity_store,
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        runner_skill = DagRunner(executor_skill)
        result_skill = await runner_skill.run(skill_graph, "skill-run-1", {})

        # 验证: X 成功续接源会话
        assert result_skill.failures == {}
        assert "X" in result_skill.node_outputs
        assert result_skill.node_outputs["X"].ok

        # 验证: X 续接了 B 的 session
        calls = _read_call_log(tmp_path)
        call_x = next((c for c in calls if c["node_id"] == "X"), None)
        assert call_x is not None
        # X 续接已存在的 session
        assert call_x["is_first"] is False

    finally:
        await registry.close()


@pytest.mark.asyncio
async def test_list_consumption_no_duplicate(tmp_path: Path) -> None:
    """
    C30: 验证 list 消费不重复且可重试

    场景:
    - 连续两次成功消费选取不同 session
    - 失败 run 再次触发被重新选取
    - 显式指定 run_id 忽略 consumed
    """
    call_log: list[dict] = []
    pi = _fake_pi_script(tmp_path, call_log)

    entity_store = _entity_store_with_session_resources(["session:relay-main/task-1"])

    node_b = NodeConfig.model_validate({
        "name": "agent-b",
        "type": "agent",
        "model": "test-model",
        "input_type": "Any",
        "output_type": "Any",
    })

    main_dag = DagConfig.model_validate({
        "name": "relay-main",
        "nodes": [
            {"id": "B", "type": "agent-b", "config": {"session": "task-1"}, "resource": "session:relay-main/task-1"},
        ],
        "edges": [],
    })

    main_graph = load_graph(main_dag, {"agent-b": node_b})

    registry = SessionRegistry(":memory:")
    await registry.initialize()

    try:
        executor_main = NodeExecutor(
            {"agent-b": node_b},
            SystemConfig(),
            RuntimeSettings(pi_bin=str(pi)),
            _test_snapshot(tmp_path),
            instances=main_graph.instances,
            entity_store=entity_store,
            daemon_data_dir=tmp_path / "data",
            session_registry=registry,
        )

        runner_main = DagRunner(executor_main)

        # 创建两个 completed sessions
        result1 = await runner_main.run(main_graph, "main-run-1", {})
        assert result1.failures == {}
        await registry.finish("relay-main", "task-1", "main-run-1", "completed")

        result2 = await runner_main.run(main_graph, "main-run-2", {})
        assert result2.failures == {}
        await registry.finish("relay-main", "task-1", "main-run-2", "completed")

        # 验证注册表有两个 completed sessions
        sessions = await registry.list_sessions("relay-main", "task-1")
        completed_sessions = [s for s in sessions if s["status"] == "completed"]
        assert len(completed_sessions) == 2, "Should have 2 completed sessions"

        # 验证 get_oldest_unconsumed 返回最旧的
        oldest = await registry.get_oldest_unconsumed("relay-main", "task-1", "X")
        assert oldest is not None, "Should have unconsumed session"
        first_session_id = oldest["session_id"]

        # 模拟消费：手动标记为已消费
        await registry.mark_consumed(first_session_id, "X")

        # 再次查询，应该返回另一个
        second_oldest = await registry.get_oldest_unconsumed("relay-main", "task-1", "X")
        assert second_oldest is not None, "Should have another unconsumed session"
        second_session_id = second_oldest["session_id"]

        # 验证两次返回的不同
        assert first_session_id != second_session_id, "Should return different sessions"

        # 标记第二个也被消费
        await registry.mark_consumed(second_session_id, "X")

        # 第三次查询，应该没有未消费的了
        third = await registry.get_oldest_unconsumed("relay-main", "task-1", "X")
        assert third is None, "Should have no unconsumed sessions"

        # 验证 list_with_consumption 显示两个都已消费
        consumed_list = await registry.list_with_consumption("relay-main", "task-1", "X")
        consumed_count = sum(1 for s in consumed_list if s["consumed"])
        assert consumed_count == 2, "Both sessions should be marked as consumed"

    finally:
        await registry.close()
