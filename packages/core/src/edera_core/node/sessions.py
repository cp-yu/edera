"""Session 引用解析纯函数"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionResolution:
    """Session 解析结果"""
    session_dir: Path
    session_id: str | None  # None = 首次创建，非 None = 续接


def parse_session_reference(session_value: str | None) -> tuple[str, str, str | None]:
    """
    解析 session 字段值

    Returns:
        (dag_name, group, mode) 其中：
        - dag_name: 当前 DAG 名或跨 DAG 引用的源 DAG 名
        - group: session 组名
        - mode: None (同 DAG 组名) | "latest" | "list"
    """
    if not session_value:
        return ("", "", None)

    # 跨 DAG 引用: <dag_name>/<group>@latest 或 <dag_name>/<group>@list
    cross_dag_match = re.match(r'^([^/@]+)/([^/@]+)@(latest|list)$', session_value)
    if cross_dag_match:
        return (cross_dag_match.group(1), cross_dag_match.group(2), cross_dag_match.group(3))

    # 同 DAG 组名: <group>
    if '/' not in session_value and '@' not in session_value:
        return ("", session_value, None)

    raise ValueError(f"Invalid session reference format: {session_value}")


def resolve_session_path(
    root: Path,
    current_dag_name: str,
    instance_id: str,
    run_id: str,
    session_value: str | None,
) -> Path:
    """
    解析 session 路径（不查注册表，用于本地路径推导）

    未声明 session 时使用 instance_id 作为 group，路径与既有行为一致。
    同 DAG 组名使用当前 run_id。
    跨 DAG 引用的路径需要从注册表获取，这里无法推导。
    """
    dag_name, group, mode = parse_session_reference(session_value)

    # 未声明 session，使用 instance_id
    if not session_value:
        return root / "sessions" / current_dag_name / instance_id / run_id

    # 同 DAG 组名
    if not dag_name:
        return root / "sessions" / current_dag_name / group / run_id

    # 跨 DAG 引用无法本地推导
    raise ValueError(f"Cross-DAG session reference requires registry resolution: {session_value}")


def invocation_dir(session_dir: Path, node_id: str) -> Path:
    """获取节点的 invocation 目录"""
    return session_dir / "invocations" / node_id
