## 1. Core 任务

### Task 1: 重写 ResourceSemaphore

**Goal**: 将 `ResourceSemaphore` 改为自管计数 + 等待者队列，消除私有属性 hack 与广播惊群，新增阻塞式 `async acquire()`。

**Files**:
- Modify: `packages/core/src/edera_core/dag/resources.py`
- Test: `tests/core/integration/test_resource_semaphore.py`

**Requirements**:
- 自管 permit 计数，不再读写 `asyncio.Semaphore._value`
- 新增 `async acquire()`：可用立即占用，不可用挂起入队；等待中被取消时从队列移除不泄漏
- `release()` 精确唤醒队首一个等待者，不广播
- `acquire_nowait()`/`available()`/`release()` 对外接口与语义不变，调度器侧零改动
- nowait 与阻塞混用时计数一致，无丢失唤醒

#### Checks

- [ ] C1 阻塞 acquire 与精确唤醒
  - Verifies: `specs/dag-resource-semaphore/spec.md` / Requirement "阻塞式 acquire" / Scenario "阻塞等待后获得 permit"、"精确唤醒"
  - Command: `uv run pytest tests/core/integration/test_resource_semaphore.py -x -q`
  - Expect: 新增用例通过；多个等待者排队时一次 release 仅唤醒一个

- [ ] C2 混用与取消安全
  - Verifies: `specs/dag-resource-semaphore/spec.md` / Requirement "阻塞式 acquire" / Scenario "nowait 与阻塞混用"、"等待中被取消不泄漏"
  - Command: `uv run pytest tests/core/integration/test_resource_semaphore.py -x -q`
  - Expect: 交错 acquire/release 下已发放 permit 不超过 permits；取消等待者后续唤醒正常

- [ ] C3 存量回归
  - Verifies: `specs/dag-resource-semaphore/spec.md` / Requirement "Semaphore acquire/release 调度" / Scenario "acquire 成功立即启动"、"acquire 失败暂缓启动"
  - Command: `uv run pytest tests/core/integration/test_resource_semaphore.py -q`
  - Expect: 现有全部用例通过，调度器侧行为不变

### Task 2: 循环执行语义（until 封顶短路 + 迭代级持锁）

**Goal**: `_execute_parallel_loop` 实现封顶短路与迭代级 acquire；`_execute_serial_loop` 加迭代级持锁；调度层 loop 节点跳过外壳 acquire。

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `tests/core/integration/test_dag_runner.py`

**Requirements**:
- 调度层：`instance.loop != None` 时跳过节点级 `_acquire_resource`
- 并行：迭代任务逐个 `await acquire()`（无 resource 不限并发）；`as_completed` 收割，任一输出满足 `until` 即 cancel 未完成迭代；被取消迭代 release permit
- 输出形状恒为列表：until 命中 `[匹配 payload]`，跑满返回全部成功 payload 列表；`metadata.loop_until_matched` 如实标记
- 串行：每迭代 acquire/release，`until` 提前 break 语义不变
- 现有 `test_single_node_loop`（parallel count=3 / serial count=2）保持通过

#### Checks

- [ ] C4 until 封顶短路
  - Verifies: `specs/single-node-loop/spec.md` / Requirement "并行循环模式" / Scenario "条件停止并行循环（封顶短路）"、"until 跑满未命中"、"输出形状恒为列表"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py -x -q -k loop`
  - Expect: 命中时未完成迭代被取消、payload 为单元素列表；跑满返回全量列表

- [ ] C5 迭代级并发控制
  - Verifies: `specs/single-node-loop/spec.md` / Requirement "循环并发控制" / Scenario "permits 限制并发迭代数"、"permits 为 1 不死锁"、"与非循环节点共享 resource"、"串行循环迭代持锁"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py tests/core/integration/test_resource_semaphore.py -x -q`
  - Expect: permits=2/count=5 时 max_active==2；permits=1 串行跑完不死锁；共享 resource 互斥生效

- [ ] C6 循环节点外壳不抢锁
  - Verifies: `specs/dag-resource-semaphore/spec.md` / Requirement "Semaphore acquire/release 调度" / Scenario "循环节点外壳不抢锁"
  - Evidence: `packages/core/src/edera_core/dag/runner.py`
  - Expect: loop 节点启动路径不调用节点级 `_acquire_resource`，permit 仅由迭代持有

### Task 3: loop/resource 序列化往返保真

**Goal**: GET/PUT graph API 透传 `loop` 与 `resource`，修复静默丢弃。

**Files**:
- Modify: `packages/core/src/edera_core/service_common.py`
- Test: `tests/core/integration/test_dag_runner.py`（或现有 graph service 测试文件）

**Requirements**:
- `_graph_dag_state` 节点 item 输出 `loop`/`resource`
- `dag_node_payload` 白名单透传 `loop`/`resource`，非法值由 `DagConfig.model_validate` 拒绝（400）
- GET→PUT round-trip 字段保真；`loop: null` 与缺省等价

#### Checks

- [ ] C7 序列化往返
  - Verifies: `specs/single-node-loop/spec.md` / Requirement "循环配置序列化往返保真" / Scenario "GET 返回 loop 与 resource"、"PUT 往返保真"、"非法 loop 配置被拒"
  - Command: `uv run pytest tests/core -x -q -k "graph or dag"`
  - Expect: round-trip 后 loop/resource 与保存前一致；mode 非法或 count<1 返回 INVALID_ARGUMENT/400

## 2. Web 任务

### Task 4: Inspector 循环配置区块与类型透传

**Goal**: 前端类型、record 转换、Inspector 编辑区块支持 `loop`/`resource`。

**Files**:
- Modify: `apps/web-console/src/api/types.ts`
- Modify: `apps/web-console/src/features/workbench/lib/graph.ts`
- Modify: `apps/web-console/src/features/workbench/components/Inspector.tsx`
- Test: `apps/web-console/scripts/`（沿现有 verify 脚本模式）

**Requirements**:
- `NodeInstance`/`DagNodeRecord` 增加 `loop?: {mode, count?, until?}`、`resource?: string | null`
- `graph.ts` record 转换与 `Inspector.tsx` save 路径透传两字段（顶层，不入 config）
- 「循环」折叠区块：mode 下拉（无/parallel/serial）、count 数字、until 文本、resource 下拉（选项取 DAG state entities 中 type=resource 者 + 「无」）
- 实例无 loop 时区块默认收起；mode 改回「无」时清除 loop 字段

#### Checks

- [ ] C8 区块渲染与保存
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node instance loop configuration in Inspector" / Scenario "循环区块渲染"、"保存写入顶层字段"、"清除循环配置"
  - Command: `cd apps/web-console && npm run build`
  - Evidence: `apps/web-console/src/features/workbench/components/Inspector.tsx`
  - Expect: 构建通过；save 产出的 record 顶层含 loop/resource，config 中无 loop

- [ ] C9 resource 下拉选项
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Node instance loop configuration in Inspector" / Scenario "resource 下拉选项来源"
  - Evidence: `apps/web-console/src/features/workbench/components/Inspector.tsx`
  - Expect: 选项过滤自 entities 中 type=resource 者并含「无」

### Task 5: Canvas 循环徽标

**Goal**: 画布节点卡片按 loop 配置展示徽标。

**Files**:
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Modify: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`

**Requirements**:
- Canvas 节点数据透传 `loop`
- 并行 `∥ ×N`、串行 `⟳ ×N`，有 until 加条件标记；无 loop 不显示

#### Checks

- [ ] C10 徽标展示
  - Verifies: `specs/dag-workbench-ui/spec.md` / Requirement "Canvas loop badge" / Scenario "并行徽标"、"串行带条件徽标"、"无循环无徽标"
  - Command: `cd apps/web-console && npm run build`
  - Evidence: `apps/web-console/src/features/workbench/components/nodes/CustomNode.tsx`
  - Expect: 构建通过；徽标渲染逻辑按 mode/count/until 分支正确

## 3. 示例与收尾

### Task 6: 示例配置与全量回归

**Goal**: 补带 `loop` 的示例 DAG 节点，跑全量测试。

**Files**:
- Modify: `extensions/` 下示例 DAG YAML（选一处现有示例）
- Test: 全量

**Requirements**:
- 示例节点含 `loop`（并行 + count）与可选 resource 用法注释
- 示例可被 GET/PUT round-trip 保真加载
- Core 全量测试与 web 构建通过

#### Checks

- [ ] C11 示例加载
  - Verifies: `specs/single-node-loop/spec.md` / Requirement "循环配置序列化往返保真" / Scenario "GET 返回 loop 与 resource"
  - Command: `uv run pytest tests/core -q`
  - Expect: 含 loop 示例的配置正常加载，全量测试通过
