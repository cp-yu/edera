## ADDED Requirements

### Requirement: Cascade delete 降低事务性承诺
系统 SHALL 在 `DELETE /api/config/entity-types/{name}?cascade=true` 时按顺序删除类型、实例、关系，但 MUST NOT 保证跨文件原子性。中间步骤失败时 SHALL 返回错误，但已完成的写入不会自动回滚。

#### Scenario: Cascade delete 顺序持久化
- **WHEN** 前端请求 cascade delete entity type
- **THEN** 系统 SHALL 依次保存 entities.yaml（删除实例）、entity-relations.yaml（删除关系）、删除 type 文件，任一步骤失败则返回错误

#### Scenario: 中间步骤失败不回滚
- **WHEN** cascade delete 过程中第二步失败
- **THEN** 系统 SHALL 返回错误，但第一步的文件修改已持久化，不会自动恢复
