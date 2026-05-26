## ADDED Requirements

### Requirement: NodeConfig Discriminated Union 类型定义
系统 SHALL 将 NodeConfig 定义为 Pydantic Discriminated Union，以 `type` 字段作为判别器，支持 `function`、`agent`、`dag` 三种变体。每种变体 SHALL 仅包含该类型所需的字段。

#### Scenario: Function 节点配置反序列化
- **WHEN** YAML 中 `type: function` 的节点配置被加载
- **THEN** 系统反序列化为 `FunctionNodeConfig`，包含 `handler`、`parameters` 字段，不包含 `model`、`dag_ref` 字段

#### Scenario: Agent 节点配置反序列化
- **WHEN** YAML 中 `type: agent` 的节点配置被加载
- **THEN** 系统反序列化为 `AgentNodeConfig`，包含 `model`（必填）、`workdir`、`tools` 字段，不包含 `handler`、`dag_ref` 字段

#### Scenario: Dag 节点配置反序列化
- **WHEN** YAML 中 `type: dag` 的节点配置被加载
- **THEN** 系统反序列化为 `DagNodeConfig`，包含 `dag_ref`（必填）、`input_mapping` 字段，不包含 `handler`、`model` 字段

#### Scenario: 无效类型拒绝
- **WHEN** YAML 中 `type` 字段值不在 `function`/`agent`/`dag` 之中
- **THEN** 系统 SHALL 抛出 ValidationError，包含明确的类型错误信息

### Requirement: 共享基础字段
所有 NodeConfig 变体 SHALL 共享基础字段：`name`、`role`（source/processor/sink）、`input_type`、`output_type`、`optional`、`timeout_seconds`。

#### Scenario: 基础字段在所有变体中可用
- **WHEN** 任意类型的 NodeConfig 被加载
- **THEN** 该配置对象 SHALL 包含 `name`、`role`、`input_type`、`output_type` 字段

### Requirement: Rust 兼容的序列化格式
NodeConfig 的 YAML 序列化格式 SHALL 与 Rust `serde(tag = "type")` 的 internally-tagged enum 格式一致，确保同一份 YAML 可被 Python Pydantic 和 Rust serde 双向反序列化。

#### Scenario: YAML 格式兼容性
- **WHEN** NodeConfig 序列化为 YAML
- **THEN** 输出格式为 `type` 字段内联于对象顶层（internally tagged），而非外部包装（externally tagged）
