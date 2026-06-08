## MODIFIED Requirements

### Requirement: Manifest 文件解析

核心 SHALL 解析扩展目录下的 `manifest.yaml` 文件，提取 handler 声明、entity type 声明、依赖信息和 import 声明。Manifest MUST 遵循固定 schema：顶层字段 `name`（必填）、`version`（必填）、`type`（可选，默认 `handler_provider`）、`description`（可选）、`depends`（可选）、`handlers`（可选）、`entity_types`（可选）、`storage`（可选）、`imports`（可选）。`imports` 字段 MUST 支持 `entities`、`providers`、`libraries` 子字段，且所有路径支持 glob patterns。解析后的 manifest 数据 SHALL 持久化到数据库，不再构建内存 Registry。

#### Scenario: 解析完整 manifest

- **WHEN** 核心扫描到包含 `manifest.yaml` 的扩展目录，manifest 包含 `name`、`version`、`handlers`、`entity_types` 字段
- **THEN** 核心 SHALL 解析出所有 handler 描述符和 entity type 定义
- **THEN** 核心 SHALL 将 manifest 完整内容存储到 `installed_extensions.manifest_snapshot` 字段（JSON）
- **THEN** 核心不再构建 `HandlerRegistry` 和 `EntityTypeRegistry`

#### Scenario: Manifest 缺少必填字段

- **WHEN** 核心扫描到 `manifest.yaml` 缺少 `name` 或 `version` 字段
- **THEN** 核心 SHALL 拒绝加载该扩展并记录错误日志，包含文件路径和缺失字段名

#### Scenario: Manifest schema 校验失败

- **WHEN** `manifest.yaml` 中 `handlers` 条目缺少 `entry`、`role` 或 `input_type` 字段
- **THEN** 核心 SHALL 拒绝该 handler 注册并记录校验错误

#### Scenario: 解析 workflow import declarations

- **WHEN** workflow extension manifest 包含 `imports.entities`
- **THEN** 核心 SHALL 解析并保留这些 Entity import declaration
- **AND** scan 阶段 MUST NOT 直接写入 DB Entity

#### Scenario: 解析 type 字段

- **WHEN** manifest 包含 `type: workflow_extension`
- **THEN** 核心 SHALL 识别为 workflow extension 类型
- **AND** 解析 `imports.providers` 和 `imports.libraries` 字段

#### Scenario: 解析 imports.providers 并展开 glob

- **WHEN** manifest 包含 `imports.providers: ["_providers/*/manifest.yaml"]`
- **THEN** 核心 MUST 展开 glob pattern 为具体 provider 目录列表
- **AND** 递归读取每个 provider 的 manifest

#### Scenario: 解析 imports.libraries 并展开 glob

- **WHEN** manifest 包含 `imports.libraries: ["_lib/*"]`
- **THEN** 核心 MUST 展开 glob pattern 为具体 library 目录列表
- **AND** 记录每个 library 的路径到 manifest_snapshot

#### Scenario: Glob pattern 无匹配时报错

- **WHEN** manifest 包含 glob pattern 但无任何匹配路径
- **THEN** 核心 MUST 拒绝加载并报告未匹配的 pattern
