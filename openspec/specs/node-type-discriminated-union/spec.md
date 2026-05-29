# node-type-discriminated-union Specification

## Purpose
此规约记录变更 core-architecture-overhaul 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: NodeConfig Discriminated Union 类型定义

NodeConfig schema SHALL 在 `NodeConfigBase` 中增加可选 `emits` 字段，类型为 `list[EmitDeclaration]`。`EmitDeclaration` 包含 `event: str` 和 `condition: str`。现有 function/agent/dag 三种变体保持不变。

#### Scenario: function node 声明 emits

- **WHEN** node type yaml 中包含 `emits: [{event: "event:negative-news", condition: "output.sentiment == 'negative'"}]`
- **THEN** Pydantic 反序列化成功，`emits` 字段可被 DAG Runner 读取

#### Scenario: emits 字段可选

- **WHEN** node type yaml 中不包含 `emits` 字段
- **THEN** 反序列化成功，`emits` 默认为空列表

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

