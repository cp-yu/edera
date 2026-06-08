---
capabilities:
  - cap.core.extension-manifest-system
---
# extension-manifest-system Specification

## Purpose
定义 Manifest 文件解析、文件名 Fallback 机制、Handler 描述符提取、扩展依赖声明等能力。
## Requirements
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

### Requirement: Handler 描述符提取

核心 SHALL 从 manifest 的 `handlers` 段提取 `NodeTypeDescriptor`，包含 `name`、`role`、`input_type`、`output_type`。这些描述符 SHALL 存储在 `manifest_snapshot` 中，运行时通过 `DatabaseHandlerResolver` 按需查询，不再使用 node type registry。

#### Scenario: 提取 NodeTypeDescriptor

- **WHEN** manifest 声明 handler `name: fetch-rss, role: source, input_type: Any, output_type: "list[RawItem]"`
- **THEN** 核心 SHALL 构建 `NodeTypeDescriptor(name="fetch-rss", role="source", input_type="Any", output_type="list[RawItem]")`
- **THEN** 核心 SHALL 将该 descriptor 存储在 `manifest_snapshot.handlers` 列表中
- **THEN** 运行时通过查询数据库获取 descriptor，不再从内存 registry 获取

#### Scenario: 同一扩展提供多个 handler

- **WHEN** manifest 的 `handlers` 段包含多个条目
- **THEN** 核心 SHALL 为每个条目分别构建 `NodeTypeDescriptor`
- **THEN** 所有 descriptors 存储在同一个 `manifest_snapshot.handlers` 数组中

### Requirement: 扩展依赖声明

Manifest MAY 包含 `depends` 字段声明对其他扩展或 `_lib/` 模块的依赖。系统 SHALL 在安装时校验依赖是否已安装。

#### Scenario: 依赖已安装

- **WHEN** manifest 声明 `depends: [rss-fetcher]` 且 `rss-fetcher` 存在于 `installed_extensions` 表（`enabled=true`）
- **THEN** 系统 SHALL 允许安装

#### Scenario: 依赖未安装

- **WHEN** manifest 声明 `depends: [rss-fetcher]` 且 `rss-fetcher` 不在 `installed_extensions` 表中
- **THEN** 系统 MUST 拒绝安装并报告缺失的依赖

#### Scenario: _lib 依赖检查

- **WHEN** manifest 声明 `depends: [_lib/http_fetch]`
- **THEN** 系统 SHALL 检查 `extensions/_lib/http_fetch.py` 或 `handlers/_lib/http_fetch.py` 是否存在

