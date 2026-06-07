## MODIFIED Requirements

### Requirement: Node 作为 Entity 执行

Node executor SHALL 从当前 DAG run 的 `DagExecutionSnapshot` 中解析 Node type 和 handler metadata。执行入口 SHALL 通过 `snapshot.handler_resolver` 获取，MUST NOT 通过 handler registry 获取。

#### Scenario: 加载 Node Entity 并执行

- **WHEN** DAG Runner 调度执行一个 Node Entity
- **THEN** executor SHALL 从当前执行上下文解析该 Node 的 type 和 handler 字段
- **AND** executor SHALL 通过 `snapshot.handler_resolver.get(<handler>)` 查询执行入口 metadata

#### Scenario: Node Entity 无 handler 且 resolver 不存在执行入口

- **WHEN** executor 尝试执行一个无法解析 handler 的 Node Entity
- **THEN** executor SHALL 返回错误 "Entity is not executable: no registered handler" 或等价的 handler-not-found 错误
