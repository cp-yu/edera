## ADDED Requirements

### Requirement: ConfigService system config 读写
`edera-server` SHALL 通过 `ConfigService` 提供 system.toml 配置的读写操作，验证逻辑在 server 端执行。

#### Scenario: 读取 system config
- **WHEN** 客户端调用 `ConfigService.ReadSystemConfig`
- **THEN** server SHALL 返回 config/system.toml 的原始 TOML 文本内容

#### Scenario: system config 不存在
- **WHEN** 客户端调用 `ConfigService.ReadSystemConfig` 且文件不存在
- **THEN** server SHALL 返回 gRPC NOT_FOUND 错误

#### Scenario: 保存 system config
- **WHEN** 客户端调用 `ConfigService.SaveSystemConfig(content)` 携带合法 TOML 内容
- **THEN** server SHALL 通过 RuntimeConfigEditor 验证并原子写入 config/system.toml

#### Scenario: 保存非法 system config
- **WHEN** 客户端调用 `ConfigService.SaveSystemConfig` 携带不符合 SystemConfig schema 的内容
- **THEN** server SHALL 返回 gRPC INVALID_ARGUMENT 错误

### Requirement: ConfigService entity-type CRUD
`edera-server` SHALL 通过 `ConfigService` 提供 entity type 定义的完整 CRUD 操作。

#### Scenario: 列出 entity types
- **WHEN** 客户端调用 `ConfigService.ListEntityTypes`
- **THEN** server SHALL 返回 schemas/entity-types/ 目录下所有 entity type 定义

#### Scenario: 创建 entity type
- **WHEN** 客户端调用 `ConfigService.CreateEntityType(name, content)` 携带合法 YAML
- **THEN** server SHALL 验证 EntityTypeConfig schema，写入 schemas/entity-types/{name}.yaml

#### Scenario: 创建重复 entity type
- **WHEN** 客户端调用 `ConfigService.CreateEntityType` 且同名 type 已存在
- **THEN** server SHALL 返回 gRPC ALREADY_EXISTS 错误

#### Scenario: 读取 entity type
- **WHEN** 客户端调用 `ConfigService.GetEntityType(name)`
- **THEN** server SHALL 返回该 entity type 的 YAML 内容

#### Scenario: 更新 entity type
- **WHEN** 客户端调用 `ConfigService.SaveEntityType(name, content)`
- **THEN** server SHALL 验证内容并原子写入

#### Scenario: 更新 system protected entity type
- **WHEN** 客户端调用 `ConfigService.SaveEntityType` 且目标 type 标记为 system_protected
- **THEN** server SHALL 返回 gRPC PERMISSION_DENIED 错误

#### Scenario: 删除 entity type 无实例
- **WHEN** 客户端调用 `ConfigService.DeleteEntityType(name, cascade=false)` 且无实例引用
- **THEN** server SHALL 删除 entity type 文件

#### Scenario: 删除 entity type 有实例且 cascade
- **WHEN** 客户端调用 `ConfigService.DeleteEntityType(name, cascade=true)` 且有实例引用
- **THEN** server SHALL 删除 type 文件、移除所有该类型实例和相关 relation

#### Scenario: 删除 entity type 有实例无 cascade
- **WHEN** 客户端调用 `ConfigService.DeleteEntityType(name, cascade=false)` 且有实例引用
- **THEN** server SHALL 返回 gRPC FAILED_PRECONDITION 错误，包含实例数量

### Requirement: ConfigService 通用 config 读写
`edera-server` SHALL 通过 `ConfigService` 提供通用配置文件（entities、entity-relations、node、dag、skill）的读写操作。

#### Scenario: 列出配置文件
- **WHEN** 客户端调用 `ConfigService.ListConfigs`
- **THEN** server SHALL 返回 config/ 目录下可编辑配置文件列表

#### Scenario: 读取指定配置
- **WHEN** 客户端调用 `ConfigService.ReadConfig(kind, name)`
- **THEN** server SHALL 返回对应配置文件内容

#### Scenario: 保存 entities config
- **WHEN** 客户端调用 `ConfigService.SaveEntitiesConfig(json)` 携带合法 EntitiesConfig
- **THEN** server SHALL 验证 entity type 存在性和 attributes schema，原子写入 config/entities.yaml

#### Scenario: 保存 entity-relations config
- **WHEN** 客户端调用 `ConfigService.SaveEntityRelationsConfig(json)` 携带合法配置
- **THEN** server SHALL 验证引用的 entity 存在，原子写入 config/entity-relations.yaml
