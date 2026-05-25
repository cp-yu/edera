## Context

DagRunner 当前在 `_start_ready_nodes` 中对所有满足依赖的节点立即启动（无并发限制）。实际场景中存在多节点竞争同一不可并发资源的需求（V8 isolate、外部 API rate limit 等）。需要在不改变现有事件驱动执行模型的前提下，增加 semaphore gate。

现有关键结构：
- `DagNodeInstance`：节点实例声明（`config/schema.py:258`）
- `DagRunner._start_ready_nodes`：ready 节点启动入口（`dag/runner.py:198`）
- `EntityStore`：统一 Entity 存储，支持 resolve/query

## Goals / Non-Goals

**Goals:**
- 节点可声明所需资源（`resource` 字段引用 Resource Entity id）
- DagRunner 在启动节点前 acquire semaphore，完成后 release
- 同名 Resource Entity 跨 DAG 共享同一 asyncio.Semaphore 实例
- release 后自动重新检查 pending 节点（事件驱动，不轮询）
- 无 resource 声明的节点行为不变（向后兼容）

**Non-Goals:**
- 边级 resource 约束（后续迭代）
- 优先级调度（哪个等待节点先 acquire）
- Resource Entity 的动态 permits 热更新（运行中修改 permits 不影响已创建的 semaphore）

## Decisions

1. **Resource 是 Entity**：`type: "resource"`，`attributes: {permits: int}`。通过 EntityStore resolve，复用现有 Entity 生命周期和权限体系。

2. **Semaphore 池由 DagRunner 持有**：DagRunner 构造时（或首次遇到 resource 声明时）从 EntityStore resolve Resource Entity，创建 `asyncio.Semaphore(permits)` 并缓存。同一进程内所有 DagRunner 实例共享同一 semaphore 池（模块级 dict）。

3. **acquire 策略**：`_start_ready_nodes` 中，对声明了 resource 的节点调用 `semaphore.acquire()` 的非阻塞版本（`asyncio.Semaphore` 无 try_acquire，改用内部 `_value` 检查或包装为 `asyncio.wait_for(acquire(), timeout=0)`）。acquire 失败则跳过该节点，不加入 started。后续节点完成 release 时通过 queue 事件重新触发 `_start_ready_nodes`。

4. **release 时机**：`_store_result` 中，无论成功或失败，release semaphore。确保不泄漏。

5. **DagNodeInstance schema 扩展**：新增 `resource: str | None = None`，值为 Resource Entity 的 id。

## Risks / Trade-offs

- **死锁风险**：如果 DAG 拓扑中存在循环资源依赖（A 持有 R1 等 R2，B 持有 R2 等 R1），会死锁。当前 DAG 是 acyclic 的，且 resource 约束不引入新的依赖边，风险极低。
- **公平性**：多个节点等待同一 semaphore 时，唤醒顺序取决于 asyncio 内部实现（FIFO）。不保证按 DAG 拓扑顺序。对当前场景（同类 fetcher 无序）可接受。
- **跨进程不支持**：asyncio.Semaphore 是进程内的。如果未来多进程部署，需要换分布式锁。当前单进程架构下不是问题。
