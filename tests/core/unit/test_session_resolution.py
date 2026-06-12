"""C12-C16: Session 引用解析测试"""
import pytest
from pathlib import Path

from edera_core.node.sessions import (
    parse_session_reference,
    resolve_session_path,
    invocation_dir,
)


def test_parse_same_dag_group_reference():
    """组名解析：同 DAG 组名"""
    dag, group, mode = parse_session_reference("task-1")
    assert dag == ""
    assert group == "task-1"
    assert mode is None


def test_parse_cross_dag_latest_reference():
    """跨 DAG @latest 引用解析"""
    dag, group, mode = parse_session_reference("relay-main/task-1@latest")
    assert dag == "relay-main"
    assert group == "task-1"
    assert mode == "latest"


def test_parse_cross_dag_list_reference():
    """跨 DAG @list 引用解析"""
    dag, group, mode = parse_session_reference("relay-main/task-1@list")
    assert dag == "relay-main"
    assert group == "task-1"
    assert mode == "list"


def test_parse_none_session_reference():
    """未声明 session"""
    dag, group, mode = parse_session_reference(None)
    assert dag == ""
    assert group == ""
    assert mode is None


def test_parse_invalid_format_raises():
    """非法格式被拒绝"""
    with pytest.raises(ValueError, match="Invalid session reference format"):
        parse_session_reference("a/b/c@latest")

    with pytest.raises(ValueError, match="Invalid session reference format"):
        parse_session_reference("task-1@unknown")


def test_resolve_session_path_no_declaration():
    """C14: 未声明 session 行为不变"""
    root = Path("/data")
    path = resolve_session_path(root, "my-dag", "instance-A", "run-001", None)
    assert path == Path("/data/sessions/my-dag/instance-A/run-001")


def test_resolve_session_path_same_dag_group():
    """C12: 组名解析为当前 run 组路径"""
    root = Path("/data")
    path = resolve_session_path(root, "my-dag", "instance-A", "run-001", "task-1")
    assert path == Path("/data/sessions/my-dag/task-1/run-001")


def test_resolve_session_path_cross_dag_requires_registry():
    """C15: 跨 DAG 引用需要注册表解析"""
    root = Path("/data")
    with pytest.raises(ValueError, match="Cross-DAG session reference requires registry resolution"):
        resolve_session_path(root, "my-dag", "instance-A", "run-001", "relay-main/task-1@latest")


def test_invocation_dir_path():
    """Invocation 目录路径构造"""
    session_dir = Path("/data/my-dag/task-1/run-001")
    inv_dir = invocation_dir(session_dir, "node-B")
    assert inv_dir == Path("/data/my-dag/task-1/run-001/invocations/node-B")
