## Why

当前系统中，核心配置型 entities (node, dag, trigger, resource) 已经迁移到数据库（`db-backed-core-entities`），但普通业务 entities（如 stock, rss-source, api-source）仍然存储在 `config/entities.yaml` 文件中。Entity relations 存储在 `config/entity-relations.yaml` 文件中。这导致系统存在双轨制：核心 entities 在数据库，业务 entities 在文件系统，架构不统一。需要将所有 entities 和 relations 迁移到数据库，实现统一的数据源架构，支持通过 Web Console 和 CLI 动态管理业务实体和关系。

## What Changes

- **BREAKING**: 移除 `config/entities.yaml` 文件，普通 entities 完全从数据库加载
- **BREAKING**: 移除 `config/entity-relations.yaml` 文件，relations 完全从数据库加载
- 新增 `entity_relations` 数据库表，存储实体关系
- 普通 entities 按 entity type 存储到动态表（已有的 ordinary entity tables 机制）
- 新增 `edera entity` CLI 子命令集：`list`, `create`, `update`, `delete`, `import`, `export`
- 新增 `edera relation` CLI 子命令集：`list`, `create`, `delete`
- 新增 Web Console 实体管理页面，支持 CRUD 操作
- 启动时从数据库加载所有 entities 和 relations，不再读取 YAML 文件
- 提供 import/export 功能，支持从 YAML 导入和导出到 YAML

## Capabilities

### New Capabilities
- `ordinary-entity-database-storage`: 普通 entities 存储到数据库动态表，按 entity type 分表
- `entity-relations-database-storage`: Entity relations 存储到 `entity_relations` 表
- `entity-cli-commands`: CLI `edera entity` 子命令集，支持 CRUD 和 import/export
- `relation-cli-commands`: CLI `edera relation` 子命令集，支持关系管理
- `entity-management-web`: Web Console 实体管理页面（可能已存在，需确认）

### Modified Capabilities
- `db-backed-core-entities`: 扩展为所有 entities（核心 + 普通）都从数据库加载
- `unified-entity-model`: EntityStore 统一从数据库查询所有 entities

## Impact

- `config/entities.yaml`: 移除文件，提供迁移脚本将内容导入数据库
- `config/entity-relations.yaml`: 移除文件，提供迁移脚本将内容导入数据库
- `packages/core/src/edera_core/config/loader.py`: 移除 `load_entities_config()` 和 `load_entity_relations_config()` 函数
- `packages/core/src/edera_core/config/entities.py`: `EntityStore` 改为从数据库查询
- `packages/core/src/edera_core/storage/entities.py`: 新增 `EntityRelation` model
- `packages/core/src/edera_core/storage/repository.py`: 新增 entity 和 relation CRUD 函数
- `packages/core/src/edera_core/cli.py`: 新增 `entity` 和 `relation` 子命令组
- `proto/edera.proto`: 新增 entity 和 relation 管理 RPC
- `apps/web-console/src/features/entities/`: 实体管理页面（可能已存在）
- 需要提供数据库迁移脚本，将现有 YAML 数据导入数据库
