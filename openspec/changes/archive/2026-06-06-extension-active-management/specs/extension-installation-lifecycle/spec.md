---
capabilities:
  - cap.core.extension-installation-lifecycle
---
# extension-installation-lifecycle Specification

## Purpose
定义扩展安装、卸载、停用、重新激活的完整生命周期管理，含 `installed_extensions` 数据模型、依赖检查和 bootstrap 加载逻辑。

## ADDED Requirements

### Requirement: installed_extensions 数据模型

系统 SHALL 使用 `installed_extensions` 表记录已安装扩展的完整状态。表 MUST 包含 `name`（UNIQUE）、`version`、`manifest_snapshot`（JSON）、`import_records`（JSON array）、`enabled`（BOOLEAN）、`installed_by`（TEXT）和 timestamps。

#### Scenario: 表结构完整

- **WHEN** 系统首次启动创建数据库
- **THEN** 系统 SHALL 创建 `installed_extensions` 表，含 `id`（INTEGER PRIMARY KEY AUTOINCREMENT）、`name`（TEXT UNIQUE NOT NULL）、`version`（TEXT NOT NULL）、`manifest_snapshot`（TEXT NOT NULL）、`import_records`（TEXT NOT NULL DEFAULT '[]'）、`enabled`（BOOLEAN DEFAULT TRUE）、`installed_by`（TEXT）、`created_at`（TEXT NOT NULL）、`updated_at`（TEXT NOT NULL）

#### Scenario: manifest_snapshot 存储完整 manifest

- **WHEN** 扩展被安装
- **THEN** 系统 SHALL 将 manifest.yaml 的完整内容序列化为 JSON 存入 `manifest_snapshot` 字段

#### Scenario: import_records 存储导入记录

- **WHEN** 扩展安装过程中导入了 Entity 实例
- **THEN** 系统 SHALL 将每条导入记录追加到 `import_records` JSON array，每条记录 MUST 包含 `import_path`、`entity_type`、`entity_id`、`entity_ref`、`content_digest`、`imported_entity_digest`、`status`

### Requirement: 扩展安装

系统 SHALL 支持从 `extensions/` 目录安装扩展到数据库。安装过程 MUST 将声明式内容写入数据库、将 handler 代码复制到 `handlers/` 目录。

#### Scenario: 安装完整扩展

- **WHEN** 用户请求安装 `extensions/rss-fetcher` 且该扩展未安装
- **THEN** 系统 SHALL 读取 `extensions/rss-fetcher/manifest.yaml`
- **AND** 系统 SHALL 写入 `installed_extensions` 表
- **AND** 系统 SHALL 将 handler 代码复制到 `handlers/rss-fetcher/`
- **AND** 系统 SHALL 将 `_lib/` 依赖复制到 `handlers/_lib/`（如尚未存在）
- **AND** 系统 SHALL 创建扩展表（如 manifest 声明了 `storage.tables`）
- **AND** 系统 SHALL 导入 Entity 实例（如 manifest 声明了 `imports.entities`）

#### Scenario: 安装前校验依赖

- **WHEN** 扩展 manifest 声明 `depends: [rss-fetcher]` 且 `rss-fetcher` 尚未安装
- **THEN** 系统 MUST 拒绝安装并报告缺失的依赖

#### Scenario: 安装前校验 manifest

- **WHEN** `extensions/<name>/manifest.yaml` 不存在或缺少必填字段
- **THEN** 系统 MUST 拒绝安装并报告错误

#### Scenario: 重复安装已有扩展

- **WHEN** 用户请求安装已存在于 `installed_extensions` 表中的扩展
- **THEN** 系统 MUST 拒绝安装并提示扩展已安装

#### Scenario: Entity 导入遵循幂等语义

- **WHEN** 安装时 import path 对应的 Entity ref 已存在于数据库
- **THEN** importer MUST NOT 覆盖已有 Entity
- **AND** 该条记录 `status` SHALL 为 `"skipped_existing"`

### Requirement: 扩展卸载

系统 SHALL 支持三种卸载策略，用户 MUST 显式选择策略，系统 MUST NOT 提供默认卸载行为。

#### Scenario: purge 策略卸载

- **WHEN** 用户以 `purge` 策略卸载扩展
- **THEN** 系统 SHALL 删除该扩展所有导入的 Entity（无论是否被用户修改）
- **AND** 系统 SHALL 删除该扩展的自定义表（`ext_*`）
- **AND** 系统 SHALL 删除 `handlers/<name>/` 目录
- **AND** 系统 SHALL 从 `installed_extensions` 表删除该记录

#### Scenario: keep-modified 策略卸载

- **WHEN** 用户以 `keep-modified` 策略卸载扩展
- **THEN** 系统 SHALL 比较每条 `import_records` 中 `imported_entity_digest` 与当前 Entity digest
- **AND** digest 相同的 Entity SHALL 被删除
- **AND** digest 不同（用户已修改）的 Entity SHALL 被保留
- **AND** `status = "skipped_existing"` 的 Entity MUST NOT 被删除
- **AND** 系统 SHALL 保留扩展表
- **AND** 系统 SHALL 删除 `handlers/<name>/` 目录
- **AND** 系统 SHALL 从 `installed_extensions` 表删除该记录

#### Scenario: deactivate 策略卸载

- **WHEN** 用户以 `deactivate` 策略卸载扩展
- **THEN** 系统 SHALL 将 `installed_extensions.enabled` 设为 `false`
- **AND** 系统 MUST NOT 删除任何 Entity、扩展表或 handler 代码
- **AND** 系统 SHALL 从运行时 registry 移除该扩展的 handler 和 entity type

#### Scenario: 卸载前依赖检查

- **WHEN** 用户请求卸载扩展 A，且已安装扩展 B 的 `manifest_snapshot.depends` 包含 A
- **THEN** 系统 MUST 阻止卸载并列出依赖扩展 B

### Requirement: 扩展重新激活

系统 SHALL 支持将已停用（`enabled=false`）的扩展重新激活。

#### Scenario: 重新激活已停用扩展

- **WHEN** 用户请求重新激活扩展且该扩展 `enabled=false`
- **THEN** 系统 SHALL 将 `installed_extensions.enabled` 设为 `true`
- **AND** 系统 SHALL 将该扩展的 handler 和 entity type 重新注册到运行时 registry

#### Scenario: 重新激活不存在的扩展

- **WHEN** 用户请求重新激活不存在于 `installed_extensions` 表中的扩展
- **THEN** 系统 MUST 拒绝并报告扩展未安装

### Requirement: Bootstrap 加载已安装扩展

系统启动时 SHALL 从 `installed_extensions` 表加载已安装且启用的扩展，构建 `HandlerRegistry` 和 `EntityTypeRegistry`。

#### Scenario: 启动加载已安装扩展

- **WHEN** 系统启动且 `installed_extensions` 表包含 `enabled=true` 的记录
- **THEN** 系统 SHALL 从 `manifest_snapshot` 读取 handler 定义
- **AND** 系统 SHALL 将每个 handler 的代码路径（`handlers/<name>/<entry>`）注册到 `HandlerRegistry`
- **AND** 系统 SHALL 将每个 entity type 定义注册到 `EntityTypeRegistry`

#### Scenario: 跳过已停用扩展

- **WHEN** `installed_extensions` 表包含 `enabled=false` 的记录
- **THEN** 系统 MUST NOT 注册该扩展的 handler 和 entity type

#### Scenario: 启动时不自动扫描 extensions/

- **WHEN** 系统启动
- **THEN** 系统 MUST NOT 自动扫描 `extensions/` 目录加载扩展
- **AND** 系统 MUST NOT 调用 `scan_extensions()`

### Requirement: 热加载支持

扩展安装、卸载和停用/激活操作 SHALL 在不重启服务的情况下生效。

#### Scenario: 安装后立即可用

- **WHEN** 扩展通过 CLI 或 WebConsole 安装
- **THEN** 该扩展的 handler 和 entity type SHALL 立即注册到运行时 registry
- **AND** 新安装的 DAG/node/trigger entity SHALL 立即可被调度

#### Scenario: 卸载后立即失效

- **WHEN** 扩展被卸载或停用
- **THEN** 该扩展的 handler 和 entity type SHALL 立即从运行时 registry 移除
