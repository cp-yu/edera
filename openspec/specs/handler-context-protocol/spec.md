---
capabilities:
  - cap.core.handler-context-protocol
---
# handler-context-protocol Specification

## Purpose
定义 HandlerContext 数据结构、HandlerProtocol 接口定义、EntityStoreProtocol 接口定义、NodeInput 和 NodeOutput 数据模型等能力。
## Requirements
### Requirement: HandlerContext 数据结构
核心 SHALL 定义 `HandlerContext` dataclass 作为 handler 调用的唯一参数，MUST 包含以下字段：`input: NodeInput`、`params: dict[str, Any]`、`node_id: str`、`node_type: str`、`run_id: str`、`entity_store: EntityStoreProtocol`、`runtime: RuntimeContextProtocol`。

#### Scenario: HandlerContext 字段完整性
- **WHEN** 核心构造 `HandlerContext` 传递给 handler
- **THEN** 所有字段 MUST 已填充，`input` 包含上游 payload，`params` 包含节点配置参数，`entity_store` 提供实体查询能力，`runtime` 提供运行期事实记录能力

#### Scenario: Handler 按需取值
- **WHEN** handler 只需要 `ctx.input` 和 `ctx.params`
- **THEN** handler 可忽略其他字段，无需声明不使用的参数

### Requirement: HandlerProtocol 接口定义
`edera-types` 包 SHALL 定义 `HandlerProtocol`（`typing.Protocol`），签名为 `async def run(ctx: HandlerContext) -> Any`。所有 handler MUST 符合此 Protocol。

#### Scenario: 符合 Protocol 的 handler
- **WHEN** 扩展提供 `async def run(ctx: HandlerContext) -> list[dict]`
- **THEN** 该函数 SHALL 通过 `HandlerProtocol` 类型检查

#### Scenario: 不符合 Protocol 的 handler
- **WHEN** 扩展提供 `def run(data: dict) -> dict`
- **THEN** 核心 SHALL 在加载时检测签名不匹配并记录错误

#### Scenario: Import protocol from edera_types
- **WHEN** extension handler 导入 `HandlerProtocol`
- **THEN** import path SHALL 为 `edera_types`

### Requirement: EntityStoreProtocol 接口定义
`edera-types` 包 SHALL 定义 `EntityStoreProtocol`（`typing.Protocol`），暴露实体查询接口：`query(type: str) -> list[EntityConfig]`、`resolve(ref: str) -> EntityConfig`、`related_refs(ref: str) -> list[str]`。

#### Scenario: Handler 通过 Protocol 查询实体
- **WHEN** handler 调用 `ctx.entity_store.query("rss-source")`
- **THEN** 返回所有 `type: rss-source` 的实体列表

#### Scenario: Handler 通过 Protocol 解析引用
- **WHEN** handler 调用 `ctx.entity_store.resolve("rss-source:sample-rss")`
- **THEN** 返回对应的 `EntityConfig` 实例

#### Scenario: Import EntityStoreProtocol from edera_types
- **WHEN** extension handler 导入 `EntityStoreProtocol`
- **THEN** import path SHALL 为 `edera_types`

### Requirement: NodeInput 和 NodeOutput 数据模型
`edera-types` 包 SHALL 定义 `NodeInput`（`run_id: str`、`payload: Any`、`metadata: dict`）和 `NodeOutput`（`node_id: str`、`ok: bool`、`payload: Any`、`metadata: dict`、`error: str | None`）。

#### Scenario: NodeInput 构造
- **WHEN** DAG runner 调度一个节点
- **THEN** 核心 SHALL 构造 `NodeInput(run_id=..., payload=上游输出, metadata=上下文信息)`

#### Scenario: NodeOutput 成功
- **WHEN** handler 返回成功结果
- **THEN** 核心 SHALL 包装为 `NodeOutput(node_id=..., ok=True, payload=handler返回值, metadata=...)`

#### Scenario: NodeOutput 失败
- **WHEN** handler 抛出异常
- **THEN** 核心 SHALL 包装为 `NodeOutput(node_id=..., ok=False, error=异常信息, metadata=...)`

#### Scenario: Import models from edera_types
- **WHEN** extension handler 导入 `NodeInput` 或 `NodeOutput`
- **THEN** import path SHALL 为 `edera_types`

### Requirement: RuntimeContextProtocol 接口定义
`edera-types` 包 SHALL 定义 `RuntimeContextProtocol`，用于 handler 显式记录运行期事实。该 Protocol MUST 至少提供 `record_source_recovery(source_name: str, recovery_status: str, attempt_count: int, recoverable_reason: str | None = None, latest_failure_reason: str | None = None, escalated: bool = False, escalation_reason: str | None = None)`。

#### Scenario: Handler records source recovery
- **WHEN** source fetcher 完成一个 source 的恢复流程
- **THEN** handler SHALL 调用 `ctx.runtime.record_source_recovery(...)` 记录最终 summary

#### Scenario: Source recovery call contract
- **WHEN** handler 调用 `ctx.runtime.record_source_recovery(...)`
- **THEN** 调用 MUST 提供 `source_name`、`recovery_status` 和 `attempt_count`，并 MAY 提供 `recoverable_reason`、`latest_failure_reason`、`escalated` 和 `escalation_reason`

#### Scenario: Runtime context supplies current node identity
- **WHEN** handler 调用 `ctx.runtime.record_source_recovery(...)`
- **THEN** core SHALL 自动补齐当前 `run_id` 和 `node_id`

### Requirement: NodeInput runtime context references
`NodeInput.metadata` SHALL 仅保存当前节点输入上下文的轻量引用和直接上游摘要，MUST NOT 承载完整 payload 或向 output metadata 自动传播。

#### Scenario: NodeInput includes direct upstream statuses
- **WHEN** DAG runner 调度一个有直接上游的 function 节点
- **THEN** `ctx.input.metadata` SHALL 包含直接上游 edge input 摘要或 runtime entity refs

#### Scenario: Metadata not copied to output
- **WHEN** handler 返回成功 payload
- **THEN** core MUST NOT 自动将 `ctx.input.metadata` 复制到 `NodeOutput.metadata`
