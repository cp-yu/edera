## Why

当前扩展系统采用扁平化目录结构，9 个独立扩展混杂在 `extensions/` 下，导致包归属不明确、manifest 文件冗长（uzi-skill 手动列举 59 个 entity imports）、依赖关系不清晰。本次重组将扩展系统改为**分包结构**，支持 Workflow Extension 类型，内含 handler providers 和共享库，提升架构清晰度和可维护性。

## What Changes

- 重组 `extensions/` 为两个顶层 Workflow Extension 包：
  - `default-news-workflow/`：包含 7 个 handler provider 扩展 + `_lib/http_fetch` 共享库
  - `uzi-skill/`：独立完整的 workflow 扩展
- Manifest Schema 增加 `type: workflow_extension` 字段和 `imports.providers` / `imports.libraries` 声明
- Manifest `imports.entities` 支持 glob patterns（`entities/**/*.yaml`）替代手动列举
- Handler 安装路径改为命名空间模式：`data/handlers/{package}.{handler}/`
- Extension Loader 识别 `workflow_extension` 类型并递归处理内部 providers
- DatabaseHandlerResolver 适配命名空间路径查找
- Extension CLI 和 gRPC Service 支持嵌套 provider 的安装、导出和卸载

## Capabilities

### New Capabilities

- `extension-glob-imports`：Manifest imports 支持 glob patterns 展开
- `workflow-extension-type`：Workflow Extension 类型识别与嵌套 provider 处理
- `handler-namespace`：Handler 命名空间路径管理

### Modified Capabilities

- `extension-manifest-system`：Manifest schema 增加 `type`、`imports.providers`、`imports.libraries` 字段，`imports.entities` 支持 glob
- `extension-installation-lifecycle`：安装逻辑支持递归处理 `imports.providers` 和复制 `imports.libraries`
- `extension-cli-commands`：`export` 命令打包 `_providers/` 和 `_lib/`，`install` 命令处理嵌套结构
- `extension-grpc-service`：`InstallExtension` RPC 支持 `workflow_extension` 类型
- `database-handler-resolver`：Handler 查找支持命名空间路径 `{package}.{handler}`
- `default-news-workflow`：重组为包结构，manifest 使用 glob patterns
- `uzi-skill-dag-instance`：manifest 使用 glob patterns 替代 59 行手动列举

## Impact

**代码改动：**
- `edera_core/bootstrap/extension_loader.py`：增加 workflow_extension 识别和 glob 展开逻辑
- `edera_core/runtime/database_handler_resolver.py`：适配命名空间路径查找
- `edera_core/cli/extension.py`：`install`/`export` 命令支持嵌套结构
- `edera_core/grpc/extension_service.py`：`InstallExtension` RPC 适配
- `openspec/specs/extension-manifest-system/spec.md`：更新 schema 定义

**目录结构：**
- 7 个 handler providers 移入 `default-news-workflow/_providers/`
- `_lib/http_fetch` 移入 `default-news-workflow/_lib/`
- `web-scraper` 归入 `default-news-workflow` 包
- 所有 manifest.yaml 文件重写

**数据库：**
- `installed_extensions` 表的 `manifest_snapshot` 字段包含新 schema
- Handler 路径从 `data/handlers/{handler}/` 改为 `data/handlers/{package}.{handler}/`

**迁移影响：**
- 所有已安装扩展需卸载后重新安装
- 需停机执行目录重组
