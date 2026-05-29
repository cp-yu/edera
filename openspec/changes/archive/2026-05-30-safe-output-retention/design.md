## Context

Edera 将 `raw-item`、`analysis`、`advice`、`briefing` 等输出型 Entity 存储在 `node_outputs` 表，并通过 `system.toml` 的 `retention_count` 与 `retention_hours` 控制清理。当前 `DagController._run()` 在计算最终 run status 之前调用 `_persist_outputs()`，因此失败或取消的 run 也会触发 cleanup。

这会产生错误结果：失败 run 只写入部分上游输出时，cleanup 仍可能删除旧的 `advice` / `briefing`，导致结果页失去最后一批可展示内容。

## Goals / Non-Goals

**Goals:**

- 默认保留输出 720 小时。
- 只有完整 DAG 成功完成后才触发 output retention cleanup。
- 失败、取消、单节点运行和 partial retry 不触发 output retention cleanup。
- 保持 `cleanup_node_output_entities()` 的职责为执行清理，不混入 run status 判断。

**Non-Goals:**

- 不恢复已经被删除的历史数据。
- 不改变 `/api/results` 查询语义。
- 不新增数据库字段或后台定时清理任务。
- 不重构 DAG runner 或 node output 存储模型。

## Decisions

1. 在 `DagController._run()` 内先计算最终 `status`，再决定是否调用 `_persist_outputs()`。

   理由：`DagController` 拥有 run 级上下文，能判断是否为完整 DAG、是否成功。把判断放在 repository cleanup 函数里会让存储层依赖运行语义。

   替代方案：让 `cleanup_node_output_entities()` 查询 `dag_runs` 状态。拒绝此方案，因为它会扩大存储函数职责，并引入 run 表耦合。

2. 仅 `retry_nodes is None` 且 `status == "succeeded"` 时执行 retention。

   理由：partial retry 和单节点运行都不能代表完整结果集已刷新成功。只有完整 DAG 成功时，旧结果才可以按 retention 策略清理。

   替代方案：任何成功的单节点运行也触发 retention。拒绝此方案，因为单节点可能只产生 raw-item 或局部输出，仍会误删旧 briefing/advice。

3. 将 `SystemConfig.retention_hours` 默认值与项目配置统一为 720。

   理由：只改当前配置会让新环境继续默认 24 小时，问题会复现。默认 720 小时更符合开发期结果回看需求。

   替代方案：只改 `config/system.toml`。拒绝此方案，因为它不能修正默认行为。

## Risks / Trade-offs

- 失败 run 的中间输出可能保留更久 → 下一次完整成功 run 后仍按 retention 清理。
- 720 小时默认保留会增加本地数据库体积 → 仍受 `retention_count` 限制，且该值可通过 `system.toml` 调整。
- 已被删除的旧输出不会自动恢复 → 这是数据恢复问题，不纳入本变更。
