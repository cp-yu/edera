<!-- smart-routing: design-summary-found, input-length=2500+, detail-score=5/5, multi-subsystem=yes(explored), decision=proceed -->

## Why

当前扩展系统采用启动时自动扫描 `extensions/` 目录并加载所有扩展的方式，用户无法控制哪些扩展被激活。需要将扩展加载改为主动安装模式：数据库作为 Source of Truth 记录安装状态，`extensions/` 退化为扩展包仓库，handler 代码安装后复制到 `handlers/` 运行时目录。同时提供 CLI 命令集和 WebConsole 管理界面，支持扩展的安装、卸载、导入、导出全生命周期管理。

## What Changes

- **BREAKING**: 移除 `scan_extensions()` 自动扫描加载逻辑，bootstrap 改为查询 `installed_extensions` 表加载已安装扩展
- 新增 `installed_extensions` 数据库表（合并原 `extension_imports` 功能），记录安装状态、manifest 快照和导入记录
- 新增 `handlers/` 运行时代码目录，安装时将 handler 代码从 `extensions/` 复制到此处
- 新增 `edera extension` CLI 子命令集：`list`、`show`、`install`、`uninstall`、`reactivate`、`import`、`export`、`export-entities`
- 卸载提供三种策略（必选）：`purge`（全部清除）、`keep-modified`（保留修改）、`deactivate`（仅停用）
- 卸载前检查依赖关系，有依赖者时阻止卸载
- 新增 WebConsole 扩展管理页面（`/extensions`）
- 新增 gRPC `ExtensionService` 支撑 WebConsole 和 CLI 操作

## Capabilities

### New Capabilities
- `extension-installation-lifecycle`: 扩展安装、卸载、停用、重新激活的完整生命周期管理，含 `installed_extensions` 数据模型和依赖检查
- `extension-cli-commands`: CLI `edera extension` 子命令集，覆盖 list/show/install/uninstall/reactivate/import/export/export-entities
- `extension-management-web`: WebConsole 扩展管理页面，展示可用/已安装扩展，支持安装、卸载、导入、导出操作
- `extension-grpc-service`: gRPC ExtensionService，提供扩展管理 RPC 接口

### Modified Capabilities
- `extension-manifest-system`: bootstrap 流程从自动扫描改为查询 `installed_extensions` 表加载；`scan_extensions()` 替换为 `discover_available_extensions()` + `load_installed_extensions()`
- `extension-entity-imports`: 导入记录合并到 `installed_extensions.import_records` JSON 字段，移除独立的 `extension_imports` 表
- `edera-cli`: 新增 `extension` 子命令组

## Impact

- `packages/core/src/edera_core/bootstrap.py`: 重写，移除 `scan_extensions()`，新增 `discover_available_extensions()` 和 `load_installed_extensions()`
- `packages/core/src/edera_core/extension_imports.py`: 重构，导入逻辑改为安装时触发
- `packages/core/src/edera_core/engine.py`: 启动流程适配新 bootstrap
- `packages/core/src/edera_core/dag_controller.py`: 适配新 bootstrap
- `packages/core/src/edera_core/hot_reload.py`: 适配新 bootstrap
- `packages/core/src/edera_core/storage/entities.py`: 新增 `InstalledExtension` model，移除 `ExtensionImportRecord`
- `packages/core/src/edera_core/storage/repository.py`: 新增扩展安装相关 repository 函数
- `proto/edera.proto`: 新增 `ExtensionService` 定义
- `apps/web-console/src/features/extensions/`: 新增扩展管理页面
- `apps/web-console/src/api/`: 新增扩展管理 API 调用
- 所有调用 `scan_extensions()` 的测试文件需要适配
