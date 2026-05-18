## Why

当前系统是为股市分析设计的，Portfolio、Target、Source 等概念都是股市专属的。但系统的基础设计（DAG 引擎、节点系统、配置驱动）是领域无关的，应该能够支持任意领域的应用（天气监控、新闻聚合、社交媒体分析等）。需要将领域特定的概念重构为通用的实体系统，让系统成为真正的领域无关平台。

## What Changes

- **BREAKING**: 废弃 `config/portfolio.yaml`，引入统一的 `config/entities.yaml`
- **BREAKING**: Source 不再是独立概念，而是 Entity 的一种类型（`rss-source`, `web-source`）
- 引入 `schemas/entity-types/` 目录，定义可扩展的实体类型系统（stock, city, rss-source, web-source 等）
- 引入 `config/entity-relations.yaml`，定义实体之间的关系（用于自动发现和 UI 可视化）
- 引入字段级权限系统（黑名单机制，默认全可读写，特殊字段声明限制，节点实例可提权）
- 节点配置支持 `entities` 和 `entity_permissions` 字段（在 `config` 里）
- 数据模型：`RawItem.stock_codes` 改为 `RawItem.tags`（通用标记）
- Inspector UI 支持实体选择（类似 skills 的分组多选）和权限配置（按需添加覆盖）
- 实体引用支持 UUID 和业务 ID 双模式（`stock:00700.HK` 或 `550e8400-...`）

## Capabilities

### New Capabilities

- `entity-system`: 统一的实体管理系统，包括实体类型定义、实体存储、实体引用解析、字段权限控制
- `entity-relations`: 实体关系管理，支持无方向关系定义、自动发现、UI 可视化
- `entity-field-permissions`: 字段级权限系统，支持黑名单机制、节点实例提权、运行时权限检查

### Modified Capabilities

- `runtime-config-editing`: 新增实体和关系的配置编辑能力
- `dag-workbench-ui`: Inspector 新增实体选择器和权限配置器
- `node-instance-model`: 节点实例模型新增 `entities` 和 `entity_permissions` 字段
- `node-executor`: 节点执行器支持实体上下文注入和权限检查
- `data-models`: `RawItem.stock_codes` 改为 `RawItem.tags`

## Impact

**配置文件**：
- 废弃 `config/portfolio.yaml`
- 新增 `config/entities.yaml`
- 新增 `config/entity-relations.yaml`
- 新增 `schemas/entity-types/*.yaml`

**数据库**：
- `raw_items` 表：`stock_codes` 列改为 `tags`
- 可能新增 `entities` 表（如果选择数据库存储）

**API**：
- 新增实体 CRUD API（`GET/POST/PUT/DELETE /api/entities`）
- 新增关系 CRUD API（`GET/POST/PUT/DELETE /api/entity-relations`）
- 配置编辑 API 需要支持新的配置文件

**前端**：
- Inspector 组件需要新增实体选择器和权限配置器
- 可能新增实体管理页面（类似 Nodes 页面）

**节点执行**：
- 节点上下文需要提供实体访问接口（`context.get_entity()`, `context.save_entity()`）
- 需要实现权限检查逻辑（配置时和运行时）

**迁移**：
- 需要提供迁移脚本，将现有 `portfolio.yaml` 转换为新格式
