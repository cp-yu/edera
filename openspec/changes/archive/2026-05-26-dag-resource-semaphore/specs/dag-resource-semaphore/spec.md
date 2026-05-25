## ADDED Requirements

### Requirement: Resource Entity 定义

系统 SHALL 支持 `type: "resource"` 的 Entity Type，其 `attributes` MUST 包含 `permits: int`（≥1）字段，表示该资源允许的最大并发占用数。

#### Scenario: 创建 Resource Entity
- **WHEN** 用户在 `entities.yaml` 中声明 `{id: "v8_isolate", type: "resource", attributes: {permits: 1}}`
- **THEN** EntityStore MUST 能 resolve 该 Entity，且 `attributes.permits` 为 1

#### Scenario: permits 校验
- **WHEN** Resource Entity 的 `permits` 值 < 1 或非整数
- **THEN** 配置加载 MUST 报错拒绝

### Requirement: 节点 resource 声明

`DagNodeInstance` SHALL 支持可选字段 `resource: str | None`，值为 Resource Entity 的 id。未声明时默认 None（无资源约束）。

#### Scenario: 节点声明 resource
- **WHEN** DAG YAML 中节点配置 `resource: "v8_isolate"`
- **THEN** DagRunner MUST 在启动该节点前 acquire 对应 semaphore

#### Scenario: 节点未声明 resource
- **WHEN** 节点未配置 `resource` 字段
- **THEN** DagRunner MUST 按现有逻辑立即启动，无 semaphore gate

### Requirement: Semaphore acquire/release 调度

DagRunner SHALL 在启动声明了 resource 的节点前执行非阻塞 acquire。acquire 失败时 MUST 跳过该节点（不加入 started），待后续 release 事件重新触发就绪检查。

#### Scenario: acquire 成功立即启动
- **WHEN** 节点 ready 且其 resource semaphore 有可用 permit
- **THEN** DagRunner MUST acquire permit 并立即启动该节点

#### Scenario: acquire 失败暂缓启动
- **WHEN** 节点 ready 但其 resource semaphore 无可用 permit
- **THEN** DagRunner MUST 跳过该节点，不标记为 started，待 permit 释放后重新评估

#### Scenario: 节点完成后 release
- **WHEN** 声明了 resource 的节点执行完成（无论成功或失败）
- **THEN** DagRunner MUST release 该 semaphore permit，并触发 `_start_ready_nodes` 重新检查 pending 节点

#### Scenario: 异常退出不泄漏
- **WHEN** 节点因 CancelledError 或未捕获异常退出
- **THEN** DagRunner MUST 确保 semaphore permit 被 release

### Requirement: 跨 DAG 共享 semaphore

同名 Resource Entity 在同一进程内 SHALL 对应同一个 `asyncio.Semaphore` 实例。多个 DAG 并发运行时 MUST 共享该 semaphore 的 permit 池。

#### Scenario: 两个 DAG 共享同一 resource
- **WHEN** DAG-A 和 DAG-B 各有一个节点声明 `resource: "v8_isolate"`（permits=1），DAG-A 的节点正在执行
- **THEN** DAG-B 的节点 MUST 等待 DAG-A 节点完成释放后才能 acquire

#### Scenario: 不同 resource 互不影响
- **WHEN** 节点 X 声明 `resource: "v8_isolate"`，节点 Y 声明 `resource: "eastmoney_api"`
- **THEN** X 和 Y 的 semaphore MUST 独立，互不阻塞
