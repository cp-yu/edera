## ADDED Requirements

### Requirement: Entity 写操作 emit 事件

系统 SHALL 在 Entity 的 Create/Update/Delete 操作完成后自动 emit `event:entity-changed:{ref}` 事件。

#### Scenario: Entity 创建 emit

- **WHEN** 通过 `EntityService.Create` 创建一个 entity，ref 为 `stock:00700.HK`
- **THEN** 系统调用 `emit("event:entity-changed:stock:00700.HK")`

#### Scenario: Entity 更新 emit

- **WHEN** 通过 `EntityService.Update` 修改一个 entity 的 attributes
- **THEN** 系统调用 `emit("event:entity-changed:{ref}")`

#### Scenario: Entity 删除 emit

- **WHEN** 通过 `EntityService.Delete` 删除一个 entity
- **THEN** 系统调用 `emit("event:entity-changed:{ref}")`
