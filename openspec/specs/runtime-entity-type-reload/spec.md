# runtime-entity-type-reload Specification

## Purpose
此规约记录变更 registry-removal 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 提供 reload entity types API
系统 SHALL 提供 gRPC `ReloadEntityTypes` RPC，从数据库重新加载 entity type 配置到 `AppConfig.entity_types`。

#### Scenario: 调用 reload API
- **WHEN** 客户端调用 `ReloadEntityTypes()` RPC
- **THEN** 系统从 `entity_types` 表查询所有 entity type
- **THEN** 替换 `AppConfig.entity_types` 字典内容
- **THEN** 返回成功响应

#### Scenario: Reload 后新 DAG 使用新配置
- **WHEN** reload 前 entity type "my-entity" 的 schema 是 v1
- **WHEN** 数据库中 "my-entity" 更新为 schema v2
- **WHEN** 调用 reload API
- **THEN** `AppConfig.entity_types["my-entity"]` 更新为 v2
- **THEN** 下次启动的 DAG 使用 v2 schema

### Requirement: Reload 不影响正在运行的 DAG
Reload API SHALL 只更新 `AppConfig.entity_types`，不影响正在运行的 DAG 使用的快照。

#### Scenario: 运行中的 DAG 隔离
- **WHEN** DAG 正在运行，使用快照中的 entity types
- **WHEN** 调用 reload API 更新 `AppConfig.entity_types`
- **THEN** 正在运行的 DAG 继续使用快照中的旧配置
- **THEN** 不抛出异常，不产生副作用

### Requirement: Reload 需要管理员权限
`ReloadEntityTypes` RPC SHALL 要求调用者具有管理员权限。

#### Scenario: 普通用户调用被拒绝
- **WHEN** 非管理员用户调用 `ReloadEntityTypes()`
- **THEN** 系统返回 `PermissionDenied` 错误

#### Scenario: 管理员调用成功
- **WHEN** 管理员用户调用 `ReloadEntityTypes()`
- **THEN** 系统执行 reload 并返回成功

### Requirement: Reload 支持并发调用
多个并发的 reload 调用 SHALL 安全执行，最终状态一致。

#### Scenario: 并发 reload
- **WHEN** 两个客户端同时调用 `ReloadEntityTypes()`
- **THEN** 两个调用都从数据库查询最新配置
- **THEN** `AppConfig.entity_types` 最终包含最新数据
- **THEN** 不产生数据竞争或不一致

### Requirement: Reload 记录日志
Reload 操作 SHALL 记录日志，包含调用者、时间戳、更新的 entity type 数量。

#### Scenario: 记录 reload 事件
- **WHEN** 管理员调用 reload API
- **THEN** 系统记录日志：`INFO: ReloadEntityTypes called by user={user}, loaded {count} entity types`

