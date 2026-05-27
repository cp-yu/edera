## MODIFIED Requirements

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
`edera-types` 包 SHALL 定义 `NodeInput`（`cycle_id: str`、`payload: Any`、`metadata: dict`）和 `NodeOutput`（`node_name: str`、`ok: bool`、`payload: Any`、`metadata: dict`、`error: str | None`）。

#### Scenario: NodeInput 构造
- **WHEN** DAG runner 调度一个节点
- **THEN** 核心 SHALL 构造 `NodeInput(cycle_id=..., payload=上游输出, metadata=上下文信息)`

#### Scenario: NodeOutput 成功
- **WHEN** handler 返回成功结果
- **THEN** 核心 SHALL 包装为 `NodeOutput(node_name=..., ok=True, payload=handler返回值, metadata=...)`

#### Scenario: NodeOutput 失败
- **WHEN** handler 抛出异常
- **THEN** 核心 SHALL 包装为 `NodeOutput(node_name=..., ok=False, error=异常信息, metadata=...)`

#### Scenario: Import models from edera_types
- **WHEN** extension handler 导入 `NodeInput` 或 `NodeOutput`
- **THEN** import path SHALL 为 `edera_types`
