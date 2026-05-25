## Why

当前 DagRunner 对所有 ready 节点立即启动，无并发约束机制。实际场景中存在多个节点竞争同一不可并发资源的情况（如 V8 isolate 非线程安全、外部 API rate limit），需要一个通用的 semaphore 原语来声明和执行资源约束。资源作为 Entity 实例存在，跨 DAG 共享同一信号量。

## What Changes

- 新增 Resource Entity Type：`type: "resource"`，属性包含 `permits: int`（并发许可数）
- `DagNodeInstance` 新增可选字段 `resource: str`，引用 Resource Entity 的 id
- DagRunner 在 `_start_ready_nodes` 中对声明了 resource 的节点执行 semaphore acquire，acquire 失败则暂不启动，等待 release 后重新检查
- 节点执行完成后自动 release semaphore
- 同名 resource 跨 DAG 共享同一 `asyncio.Semaphore` 实例

## Capabilities

### New Capabilities
- `dag-resource-semaphore`: DAG 节点资源信号量约束，覆盖 Resource Entity 定义、节点 resource 声明、DagRunner acquire/release 调度逻辑和跨 DAG 共享语义

### Modified Capabilities
- `dag-event-driven-executor`: `_start_ready_nodes` 增加 semaphore gate 逻辑，节点完成后 release 并重新触发 ready 检查

## Impact

- `packages/core/src/stockimformation_core/config/schema.py` — `DagNodeInstance` 新增 `resource` 字段
- `packages/core/src/stockimformation_core/dag/runner.py` — acquire/release 逻辑
- `packages/core/src/stockimformation_core/config/entities.py` — Resource EntityType 注册
- `config/entity-types/` — 新增 resource.yaml 类型定义
- 现有 DAG 无 resource 声明时行为不变（向后兼容）
