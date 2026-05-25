## Context

当前 `POST /api/pipeline/dag/{dag_name}/retry` 接受单个 `node_id`，`PipelineController.retry_node()` 计算 `retry_nodes` 集合后交给 `DagRunner.run()` 的 `retry_nodes` + `prefilled_outputs` 机制执行。DagRunner 内部已天然支持任意 `retry_nodes` 集合——`allowed` 集合控制哪些节点可被调度，`prefilled_outputs` 提供外部输入。

核心改动集中在 API 层和 Controller 层的参数泛化，DagRunner 无需修改。

## Goals / Non-Goals

**Goals:**
- 将 retry API 从单节点泛化到多节点，支持 `node_ids: string[]`
- `cycle_id` 可选化，默认取最近一次非 running 的 run
- 前端支持框选/Ctrl+多选后右键触发批量重试
- API 响应返回 `retry_nodes` 完整执行集合

**Non-Goals:**
- 不改动 DagRunner 核心调度逻辑
- 不引入新的 retry mode（仍为 single/cascade）
- 不实现浮动工具栏（后续迭代）
- 不支持跨 DAG 的批量重试

## Decisions

### 1. API 参数：`node_id` → `node_ids`

直接替换，不做向后兼容。开发阶段无历史负担。

替代方案：同时支持 `node_id` 和 `node_ids` 互斥 → 增加校验复杂度，无收益。

### 2. `cycle_id` 可选化

不传时取该 DAG 最近一次 `status != 'running'` 的 PipelineRun（含 cancelled、failed、completed）。

理由：cancelled run 中已完成节点有有效 output，用户可能正是因为某节点出问题才 stop，然后想从该节点重试。

### 3. `single` 模式多节点语义

选中节点集合作为 mini sub-DAG：
- 外部输入（上游不在选中集合中）用 prefilled
- 内部按拓扑序传播新结果
- 不连通部分并行执行

实现：`retry_nodes = set(node_ids)`，DagRunner 的 `allowed` 集合天然实现此语义。

### 4. `cascade` 模式多节点语义

各节点 downstream 取并集：`retry_nodes = ∪ downstream(node_i)`

替代方案：先去冗余（剔除已被其他节点 downstream 覆盖的节点）→ 不必要，set 天然去重。

### 5. 前端交互

- 多选后右键弹出上下文菜单："重试 N 个节点" / "重试 N 个节点及下游"
- 右键点在选中集合内 → 批量操作；点在集合外 → 切换为单节点上下文
- 无可用 cycle 时菜单项置灰 + tooltip 提示
- 触发后立即清除选中态，用 `retry_nodes` 驱动"重试中"高亮，后续由 runtimeStatus 接管

## Risks / Trade-offs

- [prefilled 数据不完整] → 后端校验并返回 400，前端 toast 提示具体缺失信息
- [多节点 cascade 并集可能覆盖大量节点] → 用户通过 `retry_nodes` 响应字段可预见执行范围；后续可考虑确认弹窗
- [并发冲突：retry 时 DAG 已有 active run] → 现有 `RunAlreadyActiveError` 机制不变
