## Context

核心引擎已实现 `DagNodeInstance.loop`（`config/schema.py:354-374` 的 `DagLoopConfig`）与 runner 的并行/串行执行（`dag/runner.py`），但序列化白名单（`service_common.py` 的 `_graph_dag_state`/`dag_node_payload`）丢弃 `loop`/`resource`，Web 端零引用，且并行 `until` 实现与 spec 不符。`ResourceSemaphore`（`dag/resources.py`）采用 `_value` 私有属性 hack + Event 广播轮询，仅支持调度器侧非阻塞 acquire，无法支撑迭代级阻塞 acquire。设计共识在 explore 会话中逐节确认完毕。

## Goals / Non-Goals

**Goals:**
- `loop`/`resource` 作为实例顶层字段在 GET/PUT/Web 全链路往返保真。
- 并行 `until` 实现封顶短路语义；输出形状统一为列表。
- 循环并发控制复用 Resource Entity permits，迭代级 acquire/release，零新增配置项。
- `ResourceSemaphore` 重写为自管计数 + 等待者队列，对外接口不变。

**Non-Goals:**
- 不修 `fallback`/`fan_in_mode` 的同类序列化丢失（单独记录）。
- 不修 semaphore 热更新失效（`_SEMAPHORES` 缓存不随 permits 变更失效）。
- 不改 `DagLoopConfig` 字段集（现有 mode/count/until 已够用）。
- 不引入 sub-DAG 内部节点的 resource 闸门。

## Decisions

- **loop/resource 走顶层字段，不进 config 袋子**：与 `DagNodeInstance` Pydantic 模型一致，沿 `optional` 已趟通的前后端路径；塞进 `config` 需教 `split_instance_config` 管线特判，纯增复杂度。
- **并行 until 选封顶短路（方案 B），弃"持续启动"（方案 A）与"认现状"（方案 C）**：A 为防成本失控需新增并发上限配置项，违背 YAGNI；C 不解决条件停止诉求。B 下 count 为硬上限（until 无 count 时取默认上限），`as_completed` 收割，任一匹配即 cancel 未完成迭代。spec 措辞随之校准。
- **输出形状永远列表**：until 命中返回 `[匹配 payload]`，跑满返回全部成功 payload 列表。形状可预测对下游 input_mapping/条件路由更友好；"取第一个元素"留给下游表达。零存量影响（全库无真实 loop 用户）。
- **锁的权属规则——谁干活谁持锁**：普通节点的干活单元是节点本身，外壳 acquire 正确（现状不动）；loop 节点的干活单元是迭代，permit 全部下放迭代，外壳跳过节点级 acquire。否则 permits 实际并发为 permits-1，且 permits=1 自死锁（外壳持唯一 permit 等迭代，迭代等外壳释放）。
- **先重写 `ResourceSemaphore` 再做迭代级 acquire**：现实现 `acquire_nowait` 手动 `_value -= 1` 绕过 CPython Semaphore 的 waiter 簿记，混用官方 `await acquire()` 会破坏不变量；Event 广播存在惊群与 set/clear 窗口的理论丢失唤醒。重写为自管计数 + 等待者队列（release 精确唤醒队首），`acquire_nowait`/`available`/`release` 接口不变（调度器侧零改动），新增 `async acquire()` 供迭代使用。
- **串行循环也做迭代级 acquire/release**：意义不在并发（天然为 1）而在跨 DAG/跨节点互斥——共享同一 resource 的其他持有者与串行迭代公平排队。
- **Inspector resource 下拉选项取自 DAG state 中 `type=resource` 的 entities**：GET 已返回 entities 列表，无需新 API。

## Risks / Trade-offs

- `ResourceSemaphore` 重写触及所有 resource 节点的调度路径。→ 对外接口不变 + `test_resource_semaphore.py` 全量回归 + 新增 nowait/阻塞混合路径用例。
- until 短路 cancel 可能留下半完成副作用（已发请求、已写 entity）。→ 协作式 cancel 与 executor 现有超时路径同质，非新风险面；文档标注 until 适合幂等节点。
- 限并发需先建 Resource Entity，多一步操作。→ 换来跨 DAG 统一的资源语义与零新增配置项。
- 序列化白名单放宽后旧 YAML round-trip。→ Pydantic 默认值兜底，`loop: null` 与缺省等价，round-trip 测试覆盖。
