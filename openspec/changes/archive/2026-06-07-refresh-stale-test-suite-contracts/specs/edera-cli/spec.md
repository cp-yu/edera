## MODIFIED Requirements

### Requirement: Entity YAML 文件工作流

`edera entity` SHALL 支持完整 Entity 文档格式的 YAML import、export 和 template 命令。CLI 数据操作 MUST 通过 gRPC 调用 `edera-server`，MUST NOT 直接读取运行时配置目录作为 source of truth。`edera entity import --file` SHALL 调用 entity import RPC，而不是退化为本地 YAML 校验后调用 create RPC。

#### Scenario: Import entity from YAML file
- **WHEN** 用户执行 `edera entity import --file node.yaml`
- **THEN** CLI SHALL 通过 `GrpcClient.entity_import` 将完整 Entity 文档提交给 server
- **AND** server SHALL 将 Entity 写入对应 DB table

#### Scenario: Imported entity is queryable
- **WHEN** 用户先通过 `edera entity import --file stock.yaml` 显式导入 `stock:TEST`
- **THEN** 后续 `edera entity query "type=stock"` SHALL 通过 gRPC 返回该显式导入的 Entity

#### Scenario: Export entity to YAML file
- **WHEN** 用户执行 `edera entity export node:reader --file node.yaml`
- **THEN** CLI SHALL 通过 gRPC 从 server 获取 Entity
- **AND** CLI SHALL 写出完整 Entity YAML 文档

#### Scenario: Export template from entity type
- **WHEN** 用户执行 `edera entity template --type node --file node.yaml`
- **THEN** CLI SHALL 通过 gRPC 请求 server 根据 EntityType 生成模板
- **AND** CLI SHALL 写出可被 `edera entity import --file` 消费的完整 Entity YAML 文档

#### Scenario: Reject invalid import file
- **WHEN** `edera entity import --file bad.yaml` 中缺少 `type` 或 `attributes`
- **THEN** 系统 MUST 拒绝导入并返回非零状态
