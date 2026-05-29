## MODIFIED Requirements

### Requirement: NodeConfig Discriminated Union 类型定义

NodeConfig schema SHALL 在 `NodeConfigBase` 中增加可选 `emits` 字段，类型为 `list[EmitDeclaration]`。`EmitDeclaration` 包含 `event: str` 和 `condition: str`。现有 function/agent/dag 三种变体保持不变。

#### Scenario: function node 声明 emits

- **WHEN** node type yaml 中包含 `emits: [{event: "event:negative-news", condition: "output.sentiment == 'negative'"}]`
- **THEN** Pydantic 反序列化成功，`emits` 字段可被 DAG Runner 读取

#### Scenario: emits 字段可选

- **WHEN** node type yaml 中不包含 `emits` 字段
- **THEN** 反序列化成功，`emits` 默认为空列表
