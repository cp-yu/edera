# handler-context-protocol Specification

## Purpose
此规约记录变更 core-extension-separation 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: HandlerContext 数据结构

核心 SHALL 定义 `HandlerContext` dataclass 作为 handler 调用的唯一参数，MUST 包含以下字段：`input: NodeInput`、`params: dict[str, Any]`、`node_name: str`、`node_type: str`、`cycle_id: str`、`entity_store: EntityStoreProtocol`。

#### Scenario: HandlerContext 字段完整性

- **WHEN** 核心构造 `HandlerContext` 传递给 handler
- **THEN** 所有字段 MUST 已填充，`input` 包含上游 payload，`params` 包含节点配置参数，`entity_store` 提供实体查询能力

#### Scenario: Handler 按需取值

- **WHEN** handler 只需要 `ctx.input` 和 `ctx.params`
- **THEN** handler 可忽略其他字段，无需声明不使用的参数

### Requirement: HandlerProtocol 接口定义

`stockimformation-types` 包 SHALL 定义 `HandlerProtocol`（`typing.Protocol`），签名为 `async def run(ctx: HandlerContext) -> Any`。所有 handler MUST 符合此 Protocol。

#### Scenario: 符合 Protocol 的 handler

- **WHEN** 扩展提供 `async def run(ctx: HandlerContext) -> list[dict]`
- **THEN** 该函数 SHALL 通过 `HandlerProtocol` 类型检查

#### Scenario: 不符合 Protocol 的 handler

- **WHEN** 扩展提供 `def run(input_data, parameters)` （同步、多参数）
- **THEN** 核心 SHALL 在加载时检测签名不匹配并记录错误

### Requirement: EntityStoreProtocol 接口定义

`stockimformation-types` 包 SHALL 定义 `EntityStoreProtocol`（`typing.Protocol`），暴露实体查询接口：`query(type: str) -> list[EntityConfig]`、`resolve(ref: str) -> EntityConfig`、`related_refs(ref: str) -> list[str]`。

#### Scenario: Handler 通过 Protocol 查询实体

- **WHEN** handler 调用 `ctx.entity_store.query("rss-source")`
- **THEN** 返回所有 `type: rss-source` 的实体列表

#### Scenario: Handler 通过 Protocol 解析引用

- **WHEN** handler 调用 `ctx.entity_store.resolve("rss-source:sample-rss")`
- **THEN** 返回对应的 `EntityConfig` 实例

### Requirement: NodeInput 和 NodeOutput 数据模型

`stockimformation-types` 包 SHALL 定义 `NodeInput`（`cycle_id: str`、`payload: Any`、`metadata: dict`）和 `NodeOutput`（`node_name: str`、`ok: bool`、`payload: Any`、`metadata: dict`、`error: str | None`）。

#### Scenario: NodeInput 构造

- **WHEN** 核心为节点准备输入
- **THEN** 核心 SHALL 构造 `NodeInput(cycle_id=..., payload=上游输出, metadata=上下文信息)`

#### Scenario: NodeOutput 成功

- **WHEN** handler 返回结果
- **THEN** 核心 SHALL 包装为 `NodeOutput(node_name=..., ok=True, payload=handler返回值, metadata=...)`

#### Scenario: NodeOutput 失败

- **WHEN** handler 抛出异常
- **THEN** 核心 SHALL 包装为 `NodeOutput(node_name=..., ok=False, error=异常信息, metadata=...)`

