## REMOVED Requirements

### Requirement: 提供 reload entity types API
**Reason**: EntityType 以 DB-backed source of truth 生效，运行时不再维护可原地 mutate 的 `AppConfig.entity_types`。
**Migration**: 删除 `ReloadEntityTypes` RPC、handler、client wrapper 和调用方；DAG run 启动时从 DB 读取并冻结 EntityType 到 `DagExecutionSnapshot`。

### Requirement: Reload 不影响正在运行的 DAG
**Reason**: 正在运行的 DAG 隔离语义由 `DagExecutionSnapshot` 承担，不再由 reload API 更新 `AppConfig.entity_types` 后保留旧快照来表达。
**Migration**: EntityType DB 变更不影响已有 `DagExecutionSnapshot`；新 run 创建新的 `DagExecutionSnapshot`。

### Requirement: Reload 需要管理员权限
**Reason**: `ReloadEntityTypes` RPC 被删除，管理员权限检查不再有对应入口。
**Migration**: EntityType CRUD 权限由 EntityType/ConfigService 的 DB-backed 写路径承担。

### Requirement: Reload 支持并发调用
**Reason**: `ReloadEntityTypes` RPC 被删除，不再存在并发 reload 调用。
**Migration**: 并发 EntityType 写入按 DB transaction 和 repository 规则处理。

### Requirement: Reload 记录日志
**Reason**: `ReloadEntityTypes` RPC 被删除，不再记录 reload API 日志。
**Migration**: EntityType 写入路径记录配置变更并 emit `event:config-changed`。

## ADDED Requirements

### Requirement: EntityType 运行时配置不依赖 reload API
系统 SHALL 以 DB-backed EntityType metadata 作为新 DAG run 的运行时 source of truth。EntityType 写入成功后 SHALL emit `event:config-changed`，MUST NOT mutate `AppConfig.entity_types` 或 rebuild `RuntimeControlSnapshot`；正在运行的 DAG MUST 继续使用启动时冻结的 `DagExecutionSnapshot`。

#### Scenario: EntityType 写入不重建控制面
- **WHEN** EntityType metadata 被保存到 DB
- **THEN** 系统 SHALL emit `event:config-changed`
- **AND** 系统 MUST NOT mutate `AppConfig.entity_types`
- **AND** 系统 MUST NOT rebuild `RuntimeControlSnapshot`

#### Scenario: 新 DAG run 使用 DB 中的新 EntityType
- **WHEN** EntityType metadata 已在 DB 中更新
- **WHEN** 后续 DAG run 启动
- **THEN** `DagExecutionSnapshot` SHALL 从 DB-backed EntityType metadata 复制新配置

#### Scenario: 运行中 DAG 不受 EntityType 变更影响
- **WHEN** DAG run 已启动并持有 `DagExecutionSnapshot`
- **WHEN** EntityType metadata 在 DB 中被修改
- **THEN** 该 DAG run MUST 继续使用快照中的旧 EntityType 配置
