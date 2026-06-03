## MODIFIED Requirements

### Requirement: Manifest 文件解析

核心 SHALL 解析扩展目录下的 `manifest.yaml` 文件，提取 handler 声明、entity type 声明、依赖信息和 import 声明。Manifest MUST 遵循固定 schema：顶层字段 `name`（必填）、`version`（必填）、`description`（可选）、`depends`（可选）、`handlers`（可选）、`entity_types`（可选）、`storage`（可选）、`imports`（可选）。

#### Scenario: 解析完整 manifest

- **WHEN** 核心扫描到包含 `manifest.yaml` 的扩展目录，manifest 包含 `name`、`version`、`handlers`、`entity_types` 字段
- **THEN** 核心 SHALL 解析出所有 handler 描述符和 entity type 定义，注册到全局 registry

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

## ADDED Requirements

### Requirement: Workflow package import boundary
Workflow extension package SHALL use manifest `imports.entities` as the only normative list of extension-owned Entity files. Runtime migration MUST NOT rely on scanning every YAML file under the extension directory, and workflow packages MUST NOT keep migrated DAG/node/trigger/resource instances as top-level `config/` runtime sources.

#### Scenario: Import list is explicit
- **WHEN** a workflow extension contains Entity YAML files under `entities/`
- **THEN** only files listed in manifest `imports.entities` SHALL be eligible for automatic import
- **AND** unlisted YAML files MUST NOT be imported implicitly

#### Scenario: Top-level config is not duplicated
- **WHEN** a DAG/node/trigger/resource instance has been moved into a workflow extension package
- **THEN** the same instance MUST NOT remain as a runtime-authoritative top-level `config/` source
