"""Integration test for session-relay-test extension"""
from pathlib import Path

import pytest

from edera_core.config.loader import _load_runtime_base_config, load_runtime_app_config
from edera_core.dag.loader import load_graph
from edera_core.extension_manager import ExtensionManager
from edera_core.storage import create_engine, init_db, sqlite_url


@pytest.fixture
async def runtime_config(tmp_path: Path):
    """Load extension and prepare runtime config"""
    # Use root directory paths, not test paths
    root_dir = Path(__file__).parent.parent.parent.parent
    extension_dir = root_dir / "extensions"
    config_dir = root_dir / "config"

    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        base = _load_runtime_base_config(config_dir)
        manager = ExtensionManager(
            extensions_dir=extension_dir,
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types=base.entity_types,
        )
        await manager.install("session-relay-test", installed_by="test")
        config = await load_runtime_app_config(config_dir, engine, [extension_dir])
        yield config
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_extension_install(runtime_config):
    """
    C31: 验证扩展安装后 DAG 可用

    验证扩展安装后 relay-main 与 relay-skill 可被列出
    """
    config = runtime_config

    # 验证 DAG 定义已加载
    assert "relay-main" in config.dags, "relay-main DAG should be loaded"
    assert "relay-skill" in config.dags, "relay-skill DAG should be loaded"

    # 验证节点定义已加载
    assert "seed-node" in config.nodes
    assert "condition-node" in config.nodes
    assert "agent-b-node" in config.nodes
    assert "agent-d-node" in config.nodes
    assert "agent-x-node" in config.nodes


@pytest.mark.asyncio
async def test_relay_main_topology(runtime_config):
    """
    C32: 验证 relay-main 接力与条件边

    验证:
    - DAG 拓扑正确：a → B → c → D
    - B 和 D 配置了 session: task-1
    - c → D 边有条件
    - B 和 D 引用相同的 session resource
    """
    config = runtime_config

    # Load relay-main DAG
    dag_config = config.dags["relay-main"]
    graph = load_graph(dag_config, config.nodes)

    # 验证节点
    assert set(graph.nodes) == {"a", "B", "c", "D"}

    # 验证边
    assert "B" in graph.edges["a"]
    assert "c" in graph.edges["B"]
    assert "D" in graph.edges["c"]

    # 验证 B 和 D 的 session 配置
    assert graph.instances["B"].config.get("session") == "task-1"
    assert graph.instances["D"].config.get("session") == "task-1"

    # 验证 B 和 D 共享相同的 resource
    assert graph.instances["B"].resource == "session:relay-main/task-1"
    assert graph.instances["D"].resource == "session:relay-main/task-1"

    # 验证条件边
    c_to_d_edge = None
    for edge in dag_config.edges:
        if edge.from_ == "c" and edge.to == "D":
            c_to_d_edge = edge
            break

    assert c_to_d_edge is not None, "c → D edge should exist"
    assert c_to_d_edge.condition is not None, "c → D should have condition"
    assert "condition_met" in c_to_d_edge.condition, "Condition should reference condition_met"


@pytest.mark.asyncio
async def test_relay_skill_topology(runtime_config):
    """
    C33: 验证 relay-skill 跨 DAG 消费

    验证:
    - X 配置了 relay-main/task-1@latest
    - X 引用相同的 session resource
    """
    config = runtime_config

    # Load relay-skill DAG
    skill_dag = config.dags["relay-skill"]
    skill_graph = load_graph(skill_dag, config.nodes)

    # 验证节点
    assert set(skill_graph.nodes) == {"X"}

    # 验证 X 的 session 配置
    assert skill_graph.instances["X"].config.get("session") == "relay-main/task-1@latest"

    # 验证 X 引用源组的 resource
    assert skill_graph.instances["X"].resource == "session:relay-main/task-1"
