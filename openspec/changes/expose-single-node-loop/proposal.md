<!-- propose-routing: source=explore-design-summary; input-length=conversation; detail-score=5/5; multi-subsystem=no; decision=proceed -->
## Why

核心引擎已实现单节点循环（`DagNodeInstance.loop`，runner 的并行/串行执行），但整条可见性链路缺失：GET/PUT `/api/graph/dag` 不序列化 `loop`/`resource`（Workbench 保存任何节点会**静默清空**手写 YAML 中的循环配置），Web Inspector 无编辑入口，示例配置为零。同时并行 `until` 实现与 spec 不符（仅事后打标记，不会提前停止），且循环并发控制依赖的 `ResourceSemaphore` 存在私有属性 hack 与惊群缺陷，无法支撑迭代级 acquire。

## What Changes

- 修复 `_graph_dag_state` / `dag_node_payload` 序列化白名单，`loop`/`resource` 往返保真（修静默丢弃 bug，CLI `dag save/export` 同管线自动受益）
- 并行 `until` 语义校准为封顶短路：count 为硬上限，任一迭代输出匹配即 cancel 其余迭代；输出形状统一为列表（命中返回 `[匹配 payload]`）
- 循环并发控制复用 Resource Entity：loop 节点外壳不抢锁，每个迭代 acquire/release 一个 permit（permits = 最大并发迭代数），零新增配置项
- `ResourceSemaphore` 重写：自管计数 + 等待者队列，消除 `_value` 私有属性 hack 与 Event 广播惊群；对外接口不变，新增 `async acquire()`
- Web Inspector 新增「循环」折叠区块（mode/count/until/resource），Canvas 节点循环徽标，前端类型与 record 转换透传两字段
- 补充带 `loop` 的示例 DAG 节点

Out-of-scope（同类存量缺陷，单独处理）：`fallback`/`fan_in_mode` 序列化丢失、semaphore 热更新失效。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `single-node-loop`: 并行 `until` 由「持续启动新实例」校准为「count 上限内短路取消」；新增输出形状语义（永远列表）、迭代级 resource 并发控制、`loop`/`resource` 序列化往返保真要求
- `dag-workbench-ui`: Inspector 新增节点实例循环配置区块（沿 instance optional 先例），Canvas 新增循环徽标展示
- `dag-resource-semaphore`: 新增阻塞式 `acquire()` 行为要求与「循环节点 permit 由迭代持有、外壳不持有」的权属规则

## Impact

- Core: `packages/core/src/edera_core/dag/resources.py`（重写）、`dag/runner.py`（调度跳过外壳 acquire、两个 loop 执行器）、`service_common.py`（序列化白名单）
- Web: `apps/web-console/src/api/types.ts`、`features/workbench/lib/graph.ts`、`components/Inspector.tsx`、`components/Canvas.tsx`、`components/nodes/CustomNode.tsx`
- 示例: `extensions/` 下示例 DAG
- 测试: `tests/core/integration/test_dag_runner.py`、`test_resource_semaphore.py` 全量回归 + 新增用例
