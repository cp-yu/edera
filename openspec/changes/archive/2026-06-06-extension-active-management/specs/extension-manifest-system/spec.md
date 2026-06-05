---
capabilities:
  - cap.core.extension-manifest-system
---
# extension-manifest-system Delta Specification

## MODIFIED Requirements

### Requirement: Manifest 文件解析

核心 SHALL 解析扩展目录下的 `manifest.yaml` 文件，提取 handler 声明、entity type 声明、依赖信息和 import 声明。Manifest MUST 遵循固定 schema：顶层字段 `name`（必填）、`version`（必填）、`description`（可选）、`depends`（可选）、`handlers`（可选）、`entity_types`（可选）、`storage`（可选）、`imports`（可选）。Manifest 解析 SHALL 仅在显式安装操作时执行，MUST NOT 在 bootstrap 时自动扫描。

#### Scenario: 安装时解析完整 manifest

- **WHEN** 用户通过 CLI 或 WebConsole 请求安装扩展，扩展目录包含合法 `manifest.yaml`
- **THEN** 系统 SHALL 解析出所有 handler 描述符和 entity type 定义
- **AND** 系统 SHALL 将解析结果写入 `installed_extensions.manifest_snapshot`

#### Scenario: Manifest 缺少必填字段

- **WHEN** 安装请求的扩展 `manifest.yaml` 缺少 `name` 或 `version` 字段
- **THEN** 系统 SHALL 拒绝安装该扩展并返回错误信息，包含文件路径和缺失字段名

#### Scenario: Manifest schema 校验失败

- **WHEN** `manifest.yaml` 中 `handlers` 条目缺少 `entry`、`role` 或 `input_type` 字段
- **THEN** 系统 SHALL 拒绝安装并返回校验错误

#### Scenario: 解析 workflow import declarations

- **WHEN** workflow extension manifest 包含 `imports.entities`
- **THEN** 系统 SHALL 解析并保留这些 Entity import declaration
- **AND** 安装过程 SHALL 通过独立 importer 处理 Entity 导入

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

## REMOVED Requirements

### Requirement: 文件名 Fallback 机制
**Reason**: 主动安装模式下所有扩展 MUST 提供 `manifest.yaml`，无 manifest 的扩展不再被支持。
**Migration**: 为现有无 manifest 的扩展创建 `manifest.yaml` 文件。

### Requirement: Manifest imports declarations
**Reason**: 功能合并到 `extension-installation-lifecycle` 的安装流程中，import declaration 解析在安装时执行而非 scan 时。
**Migration**: 无需迁移，manifest 格式不变。

### Requirement: Workflow package import boundary
**Reason**: 安装时显式导入取代了扫描时的 import boundary 约束。
**Migration**: 无需迁移，`imports.entities` 语义不变。
