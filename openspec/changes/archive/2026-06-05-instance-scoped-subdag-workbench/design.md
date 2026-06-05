## Context

当前 Workbench 的主状态只有 `selectedDagName`。Canvas、Palette、Inspector 和 BottomToolbar 都围绕这个根 DAG 名称取数。右键菜单只持有 `kind/id/x/y`，runtime status 通过 `/api/graph/runtime-status` 获取最近一次 DAG run，并按 `node_name` 建立状态表。

这对普通 DAG 足够，但对 sub-DAG 不够。`dagA.nodeX` 和 `dagB.nodeY` 可以同时引用 `common-subdag`，两者内部节点 ID 相同但 child run 不同。进入 sub-DAG 时如果只切换到 `common-subdag`，前端会读取最近一次 `common-subdag` 状态，可能显示另一个父实例的运行结果。

## Goals / Non-Goals

**Goals:**

- DAG Entity 能作为 Workbench 可拖入节点候选。
- Sub-DAG 节点实例保存和回显 `dag_ref/input_mapping`。
- 右键进入 sub-DAG 时建立实例作用域上下文，而不是裸 `dag_name` 切换。
- 子图 Canvas、Inspector Runtime 和边状态使用 child `run_id` 查询节点状态。
- 保留现有根 DAG 选择器和根视图运行控制。

**Non-Goals:**

- 不改变 DagRunner 的执行拓扑、递归深度、source/sink 映射语义。
- 不实现跨层级编辑时自动同步父子 DAG 的所有布局。
- 不新增营销式或独立页面；仍在现有 Workbench 内完成导航。
- 不支持同时打开多个 sub-DAG tab。

## Decisions

1. 使用实例作用域导航栈，而不是把 sub-DAG 当普通 `selectedDagName`。

   选择：新增 Workbench 视图上下文，根层仍是 `selectedDagName`，进入 sub-DAG 后记录 `{parentDagName, parentNodeId, parentRunId, childDagName, childRunId}`。Canvas 取图使用 `childDagName`，runtime status 使用 `childRunId`。

   备选：直接 `setSelectedDag(dag_ref)`。拒绝原因是同一个 DAG 被多个实例复用时无法知道当前要展示哪个 child run。

2. Runtime status 增加 `run_id` 作用域。

   选择：保留现有无参 runtime-status 行为，同时支持按 run_id 查询指定 run 的 `NodeRun`。Workbench 根视图继续使用当前 DAG run；sub-DAG 视图使用父节点 metadata 中的 `sub_dag_run_id`。

   备选：按 `dag_name` 查最近 run。拒绝原因是无法区分 `dagA.nodeX -> common-subdag` 和 `dagB.nodeY -> common-subdag`。

3. DAG Palette 复用节点 prototype 流程，但使用明确的 DAG prototype 类型。

   选择：前端将 DAG 列表映射为可拖拽候选，创建实例时写入 `type: "dag"`、`dag_ref: <dagName>`，并设置可读 alias。后端 graph SAVE/GET 负责保留实例字段。

   备选：为每个 DAG 创建持久 NodeConfig。拒绝原因是会把 DAG Entity 和 Node type Entity 混在一起，增加同步和删除约束。

4. 保存路径保留结构性字段。

   选择：`DagNodeRecord`、`toDagDraft()`、`dag_node_payload()` 和 graph response 都显式携带 `dag_ref/input_mapping`。实例层字段优先；没有实例 `dag_ref` 时允许从 DAG node type 的 `dag_ref` fallback。

## Risks / Trade-offs

- [Risk] 父 run 尚未执行或父节点未产出 `sub_dag_run_id` 时没有 child run 可展示 → 菜单仍可进入结构视图，但 Runtime 显示空态并说明无实例运行。
- [Risk] 保存 DAG 时遗漏 `dag_ref/input_mapping` 会破坏 sub-DAG 节点 → 后端和前端都增加 round-trip 测试。
- [Risk] RuntimeStatus API 改动影响旧调用方 → 保留无参查询语义，新增 run_id 作用域作为兼容扩展。
- [Risk] Palette 中 DAG 候选可能允许自引用或形成嵌套环 → 复用后端 `validate_sub_dag_nesting`，保存失败时返回明确错误；前端可先过滤当前 DAG 作为直接候选。
