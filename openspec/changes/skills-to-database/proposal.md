## Why

当前系统中，skills 配置存储在 `config/skills/*.yaml` 文件中，启动时从文件系统加载。这导致：1) 无法通过 Web Console 或 CLI 动态管理 skills；2) 与已经迁移到数据库的其他配置（entities, handlers）架构不统一；3) 修改 skill 需要重启系统。需要将 skills 迁移到数据库，支持运行时动态管理，Agent 执行时从数据库查询 skill 配置并动态生成文件。Skills 可以是多文件结构（文件夹），每个 skill 包含主文件 `SKILL.md` 及其他辅助文件。

## What Changes

- **BREAKING**: 移除 `config/skills/*.yaml` 文件，skills 完全从数据库加载
- 新增 `skills` 数据库表，存储 skill 配置（支持多文件结构，config_body 存储文件数组）
- 新增 `edera skill` CLI 子命令集：`list`, `show`, `create`, `update`, `delete`, `import-dir`, `import-batch`, `export`
- Agent 执行时从数据库查询 skill 配置，动态生成完整 skill 文件夹到临时目录
- 新增 Web Console skill 管理页面，支持 CRUD 操作（暂不支持多文件 skill 导入，提示使用 CLI）
- 启动时从数据库加载所有 skills，不再读取文件系统
- 提供 import/export 功能，支持文件夹导入和导出
- Skill reload API：`POST /admin/reload-skills` 刷新运行时 skill 配置
- 用户需主动通过 CLI 导入 skills，不自动迁移

## Capabilities

### New Capabilities
- `skill-database-storage`: Skills 存储到 `skills` 数据库表
- `skill-cli-commands`: CLI `edera skill` 子命令集，支持 CRUD 和 import/export
- `skill-dynamic-generation`: Agent 执行时从数据库动态生成 skill 文件
- `skill-management-web`: Web Console skill 管理页面
- `runtime-skill-reload`: 运行时刷新 skill 配置的 API

### Modified Capabilities
- `skill-registry`: 从文件系统加载改为从数据库加载

## Impact

- `config/skills/*.yaml`: 移除所有 skill 文件，用户需通过 CLI 主动导入到数据库
- `packages/core/src/edera_core/config/loader.py`: 移除 `load_skill_configs()` 函数
- `packages/core/src/edera_core/storage/entities.py`: 新增 `Skill` model（支持多文件结构）
- `packages/core/src/edera_core/storage/repository.py`: 新增 skill CRUD 函数
- `packages/core/src/edera_core/cli.py`: 新增 `skill` 子命令组（import-dir, import-batch, export）
- `proto/edera.proto`: 新增 skill 管理 RPC 和 reload RPC
- `apps/web-console/src/features/skills/`: 新增 skill 管理页面（暂不支持多文件 skill，显示限制提示）
- Agent 执行相关代码：从数据库查询 skill 并生成完整临时文件夹
