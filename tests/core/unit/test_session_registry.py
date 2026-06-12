import pytest
from pathlib import Path

from edera_core.storage import SessionRegistry


@pytest.fixture
async def registry():
    """C5-C8: 内存数据库fixture"""
    reg = SessionRegistry(":memory:")
    await reg.initialize()
    return reg


@pytest.mark.asyncio
async def test_register_and_finish_session(registry):
    """C5: 验证注册与状态流转"""
    # 创建时登记 active
    await registry.register("test-dag", "task-1", "run-001", "session-abc", "/path/to/session")

    sessions = await registry.list_sessions("test-dag", "task-1")
    assert len(sessions) == 1
    assert sessions[0]["status"] == "active"
    assert sessions[0]["session_id"] == "session-abc"

    # Run 结束更新状态
    await registry.finish("test-dag", "task-1", "run-001", "completed")

    sessions = await registry.list_sessions("test-dag", "task-1")
    assert sessions[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_reconcile_orphan_active(registry):
    """C6: 验证启动对账清理残留"""
    # 创建两条 active 记录
    await registry.register("dag-1", "task-1", "run-001", "session-1", "/path/1")
    await registry.register("dag-1", "task-1", "run-002", "session-2", "/path/2")

    # 模拟启动对账，只有 run-002 是活跃的
    await registry.reconcile_on_startup({"run-002"})

    sessions = await registry.list_sessions("dag-1", "task-1")
    assert len(sessions) == 2

    # run-001 应该变为 failed，run-002 仍为 active
    statuses = {s["run_id"]: s["status"] for s in sessions}
    assert statuses["run-001"] == "failed"
    assert statuses["run-002"] == "active"


@pytest.mark.asyncio
async def test_latest_returns_most_recent_completed(registry):
    """C7: 验证 latest 只取最近 completed"""
    import asyncio

    # 创建多条记录，使用延迟确保时间戳不同
    await registry.register("dag-1", "task-1", "run-001", "session-1", "/path/1")
    await registry.finish("dag-1", "task-1", "run-001", "completed")
    await asyncio.sleep(0.01)

    await registry.register("dag-1", "task-1", "run-002", "session-2", "/path/2")
    await registry.finish("dag-1", "task-1", "run-002", "completed")
    await asyncio.sleep(0.01)

    await registry.register("dag-1", "task-1", "run-003", "session-3", "/path/3")
    await registry.finish("dag-1", "task-1", "run-003", "failed")

    # latest 应返回最近的 completed (run-002)
    result = await registry.get_latest("dag-1", "task-1")
    assert result is not None
    assert result["session_id"] == "session-2"
    assert result["run_id"] == "run-002"


@pytest.mark.asyncio
async def test_latest_returns_none_when_no_completed(registry):
    """C7: 验证无可用记录"""
    await registry.register("dag-1", "task-1", "run-001", "session-1", "/path/1")
    await registry.finish("dag-1", "task-1", "run-001", "failed")

    result = await registry.get_latest("dag-1", "task-1")
    assert result is None


@pytest.mark.asyncio
async def test_consumption_tracking(registry):
    """C8: 验证消费账本登记与过滤"""
    # 创建两个 completed session
    await registry.register("dag-1", "task-1", "run-001", "session-1", "/path/1")
    await registry.finish("dag-1", "task-1", "run-001", "completed")

    await registry.register("dag-1", "task-1", "run-002", "session-2", "/path/2")
    await registry.finish("dag-1", "task-1", "run-002", "completed")

    # 成功后登记消费
    await registry.mark_consumed("session-1", "consumer-node")

    # list 应显示 consumed 标记
    result = await registry.list_with_consumption("dag-1", "task-1", "consumer-node")
    assert len(result) == 2

    consumed_flags = {r["session_id"]: r["consumed"] for r in result}
    assert consumed_flags["session-1"] == 1
    assert consumed_flags["session-2"] == 0

    # 默认取最旧未消费 (session-2)
    oldest_unconsumed = await registry.get_oldest_unconsumed("dag-1", "task-1", "consumer-node")
    assert oldest_unconsumed is not None
    assert oldest_unconsumed["session_id"] == "session-2"


@pytest.mark.asyncio
async def test_consumption_idempotent(registry):
    """C8: 失败不登记可重试 - 幂等性"""
    await registry.register("dag-1", "task-1", "run-001", "session-1", "/path/1")
    await registry.finish("dag-1", "task-1", "run-001", "completed")

    # 多次调用 mark_consumed 应该是幂等的
    await registry.mark_consumed("session-1", "consumer-node")
    await registry.mark_consumed("session-1", "consumer-node")

    result = await registry.list_with_consumption("dag-1", "task-1", "consumer-node")
    assert len(result) == 1
    assert result[0]["consumed"] == 1


@pytest.mark.asyncio
async def test_no_ttl_cleanup_logic():
    """C9: 确认本变更不引入 session TTL 清理承诺"""
    # 此测试仅为文档目的，验证代码中不存在 TTL 相关逻辑
    from edera_core.storage import repository
    import inspect

    source = inspect.getsource(repository)
    assert "ttl" not in source.lower() or "session" not in source.lower()
