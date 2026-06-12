from edera_core.config.schema import DagConfig, DagNodeInstance


def inject_implicit_session_resources(dag_config: DagConfig) -> dict[str, DagNodeInstance]:
    """为 session 组自动注入隐式 resource"""
    result = {}

    for instance in dag_config.nodes:
        session_value = instance.config.get("session") if isinstance(instance.config, dict) else None

        if not session_value or not isinstance(session_value, str):
            # 无 session 声明，保持原样
            result[instance.id] = instance
            continue

        # 解析 session 字段，确定 resource 名称
        if "@" in session_value:
            # 跨 DAG 引用: relay-main/task-1@latest -> session:relay-main/task-1
            ref_part = session_value.split("@")[0]
            resource_name = f"session:{ref_part}"
        else:
            # 同 DAG 组名: task-1 -> session:{dag_name}/task-1
            resource_name = f"session:{dag_config.name}/{session_value}"

        # 合并用户 resource 和隐式 resource（按字母排序保证确定性）
        existing = instance.resource.split(",") if instance.resource else []
        if resource_name not in existing:
            existing.append(resource_name)
        existing.sort()

        # 创建新实例，更新 resource
        result[instance.id] = instance.model_copy(update={"resource": ",".join(existing)})

    return result
