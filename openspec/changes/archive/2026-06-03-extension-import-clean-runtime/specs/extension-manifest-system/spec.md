## ADDED Requirements

### Requirement: Manifest imports declarations
Manifest MAY 包含 `imports.entities` 字段声明 extension 包内要自动导入的 Entity YAML 文件列表。系统 SHALL 解析该声明并保留在 extension manifest model 中，但 manifest scan MUST NOT 直接持久化这些 Entity。

#### Scenario: Parse imports entities
- **WHEN** manifest 包含 `imports: { entities: ["dags/default/dag.yaml"] }`
- **THEN** 系统 SHALL 将该 path 解析为 manifest import declaration
- **AND** scan 结果 SHALL 继续包含既有 handler、entity type 和 storage 声明

#### Scenario: Manifest without imports remains valid
- **WHEN** manifest 不包含 `imports`
- **THEN** 系统 SHALL 按既有规则加载该 extension

#### Scenario: Scan does not import entities
- **WHEN** bootstrap scan 解析到 `imports.entities`
- **THEN** scan_extensions SHALL NOT 调用 entity repository 写入 DB
