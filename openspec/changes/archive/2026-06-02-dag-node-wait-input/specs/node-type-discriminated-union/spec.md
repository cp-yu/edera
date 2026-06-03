## ADDED Requirements

### Requirement: NodeConfig 增加 wait variant
`NodeConfig` discriminated union SHALL 在现有 `function`/`agent`/`dag` 三种变体基础上新增 `wait` variant。`WaitNodeConfig` MUST 设置 `type: Literal["wait"]`，并在 `NodeConfig._variants` 注册表中注册，使 `type: "wait"` 的配置被正确反序列化为 `WaitNodeConfig`。现有三种变体行为保持不变。

#### Scenario: 反序列化 wait variant
- **WHEN** node 配置中 `type: "wait"`
- **THEN** `NodeConfig.model_validate` SHALL 返回 `WaitNodeConfig` 实例

#### Scenario: 现有变体不受影响
- **WHEN** node 配置中 `type` 为 `function`/`agent`/`dag` 之一
- **THEN** 系统 SHALL 按原有变体反序列化，行为不变
