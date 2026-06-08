## ADDED Requirements

### Requirement: Retry 临时输入支持
系统 SHALL 在批量重试多个节点时，接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 参数用于在重试时临时覆盖或追加节点输入。

#### Scenario: 重试时传递临时输入
- **WHEN** 用户重试节点并传入 `{nodeInputs: {node_1: "entity://fix"}, appendNodes: []}`
- **THEN** 系统 SHALL 在重试时使用临时输入参数

#### Scenario: 重试时追加测试参数
- **WHEN** 用户重试节点并传入 `{nodeInputs: {analyzer: {test_mode: true}}, appendNodes: ["analyzer"]}`
- **THEN** `analyzer` 节点重试时输入为原始输入加上追加参数
