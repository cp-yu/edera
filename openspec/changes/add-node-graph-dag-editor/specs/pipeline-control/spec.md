## ADDED Requirements

### Requirement: Node Graph runtime status source
系统 SHALL 为 Node Graph 编辑器提供可映射到节点名称的运行状态数据。

#### Scenario: Load graph runtime status
- **WHEN** Node Graph 编辑器请求运行状态
- **THEN** 系统 SHALL 返回当前运行和最近运行中各 Node 的状态、错误信息和 cycle_id

#### Scenario: Unknown draft node status
- **WHEN** Node Graph 草稿中存在尚未保存或没有运行记录的节点
- **THEN** 系统 SHALL 将该节点状态展示为 `unknown`，不得伪造运行结果
