## Context

当前 `DagRunner.run()` 采用 layer-by-layer 同步循环：`topological_layers()` 分层后逐层 `asyncio.gather`。这导致：
1. 节点完成后必须等同层所有节点完成才能触发下游，浪费时间
2. 无中间控制点，stop 只能通过外部 `task.cancel()` 硬杀
3. 无法从已完成的 run 中恢复状态进行重试

前端 Inspector 当前只有 Config tab，右键菜单只有 delete/disconnect，无运行时信息展示。DAG 选择器是静态 dropdown，无创建入口。

## Goals / Non-Goals

**Goals:**
- 将 DAG 执行模型重写为 event-driven dispatcher，节点完成即触发下游
- 提供 soft stop（等当前节点完成）和 hard stop（cancel task）两级中断
- 支持从已结束的 run 中恢复状态，重试失败节点（single/cascade）
- Inspector 增加 Runtime tab 展示节点运行状态和 output entities
- 点击 edge 查看上游节点产出的 entities
- 独立历史页面展示节点运行记录
- 前端 onConnect 环检测
- DAG 创建入口

**Non-Goals:**
- 实时 WebSocket 推送（保持现有 2s 轮询）
- 节点级中断（仅 DAG 级 stop）
- DAG 模板系统
- 配置变更历史展示（由 git log 承载）
- 流式跨节点传播（通过 sub-DAG 封装解决）

## Decisions

### D1: Event-driven dispatcher 架构

**选择**：中央 dispatcher + `asyncio.Queue`

```
┌─────────────────────────────────────────────────┐
│                  DagRunner                       │
│                                                 │
│  ┌───────────┐    ┌──────────────────────┐      │
│  │  Queue    │◀───│  Node Task Complete  │      │
│  │ (events)  │    └──────────────────────┘      │
│  └─────┬─────┘                                  │
│        ▼                                        │
│  ┌───────────────────────────────────────┐      │
│  │         Dispatcher Loop               │      │
│  │  1. 消费 event                        │      │
│  │  2. 检查 stop_event                   │      │
│  │  3. 更新节点状态                      │      │
│  │  4. 评估下游节点就绪条件              │      │
│  │  5. 启动就绪节点 (create_task)        │      │
│  └───────────────────────────────────────┘      │
│                                                 │
│  stop_event: asyncio.Event (soft stop)          │
│  task.cancel(): hard stop                       │
└─────────────────────────────────────────────────┘
```

**替代方案**：引用计数 + callback（分布式触发）。放弃原因：控制流分散，stop/retry/状态追踪需要额外协调机制。

### D2: Fan-in 模式

**选择**：配置在目标节点上，`fan_in_mode: "barrier" | "accumulate"`，默认 barrier。

- **barrier**：dispatcher 维护每个节点的"待满足上游数"计数器，归零时启动节点，input 为所有上游 output 的 collect
- **accumulate**：每个上游完成时 spawn 一个 sub-task 处理该 output（并行），所有 sub-task 完成后 collect 结果发给下游

**替代方案**：配置在 edge 上。放弃原因：同一节点对不同上游采用不同策略语义混乱。

### D3: Stop 机制

**选择**：`asyncio.Event` 注入 runner 实现 soft stop，`task.cancel()` 实现 hard stop。

- Soft stop：dispatcher loop 每次迭代检查 `stop_event.is_set()`，如果 set 则不再启动新节点，等所有 in-flight 节点完成后返回
- Hard stop：`PipelineController.stop_current()` 直接 cancel task，`CancelledError` 冒泡终止 dispatcher
- API：`POST /api/pipeline/dag/{name}/stop`，body `{ "force": false }` 默认 soft，`{ "force": true }` hard

### D4: Retry 机制

**选择**：新 cycle_id + `retry_of` 字段 + 从 DB 恢复状态。

```
retry flow:
1. 创建新 PipelineRun (trigger="retry", retry_of=original_cycle_id)
2. 从 DB 加载原 cycle 中已成功节点的 NodeOutputEntity
3. 在 dispatcher 中预填这些节点为 "completed" 状态
4. 对于 cascade mode：从目标节点开始，所有下游节点标记为 "pending"
5. 对于 single mode：仅目标节点标记为 "pending"
6. 启动 dispatcher，自然调度就绪节点
```

input 重建：查询 `NodeOutputEntity WHERE node_id IN (upstreams) AND cycle_id = original`，用现有 collect 逻辑组装。

**替代方案**：
- 复用原 cycle_id（丢失失败痕迹）
- 额外持久化 input snapshot（冗余存储）

### D5: 能观性 — Inspector 扩展

**选择**：Inspector 根据选中对象类型切换内容。

- 选中 Node → 展示 Config tab + Runtime tab
- 选中 Edge → 展示 Edge Detail（上游 output entities 列表 + 跳转历史链接）
- 右键 "查看当前运行状态" → 选中节点 + 切到 Runtime tab

Runtime tab 数据源：`GET /api/graph/runtime-status`（已有）+ `GET /api/node-outputs?node_id={id}&cycle_id={current}`（新增或复用已有 entity query API）

### D6: 历史页面

**选择**：独立 route `/history/dag/{dag_name}/nodes/{node_id}`。

数据源：`NodeRun WHERE node_name = {node_id} ORDER BY started_at DESC`，每条记录可展开查看对应 cycle 的 `NodeOutputEntity`。

Edge 历史：右键 edge "查看历史" → 跳转到上游节点的历史页面，不单独建 edge 历史 route。

### D7: 前端环检测

**选择**：`onConnect` 回调中执行 DFS，检测添加新边后是否形成环。

算法：从 target 节点出发，沿 edges 做 DFS，如果能到达 source 节点则存在环。时间复杂度 O(V+E)，对于当前规模的 DAG（<50 节点）无性能问题。

### D8: 新建 DAG

**选择**：`POST /api/graph/dag`，body `{ "name": "..." }`。

后端行为：校验名称合法性（kebab-case、不重复）→ 创建 `config/dags/{name}.yaml`（`{ name, nodes: [], edges: [] }`）→ 返回空 DAG 结构。前端 dropdown 自动刷新。

### D9: 错误传播

**选择**：仅阻断失败路径下游。

dispatcher 中，节点失败时：
- 标记该节点为 failed
- 不向其下游发送完成事件（下游永远不会就绪）
- 其他独立路径不受影响
- optional 节点失败视为完成（payload=None），下游正常触发

## Risks / Trade-offs

- **[执行模型重写范围大]** → 现有 `test_dag_runner.py` 全部需要适配。缓解：新 runner 保持相同的外部接口（`DagRunner.run(graph, cycle_id, payload) -> DagRunResult`），测试只需调整内部行为断言
- **[Retry 依赖 NodeOutputEntity 完整性]** → 如果 output_recorder 在节点成功后未能持久化 entity，retry 时无法恢复该节点的 output。缓解：output_recorder 失败应标记节点为 failed
- **[Accumulate 模式下 sub-task 数量]** → fan-in 节点的上游数量决定并发 sub-task 数。缓解：当前 DAG 规模小（<10 个上游），不需要限流
- **[Soft stop 延迟]** → 如果当前节点是 LLM 调用（可能耗时 30s+），soft stop 需要等待其完成。缓解：用户可选择 hard stop 作为最后手段
