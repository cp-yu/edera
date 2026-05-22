## Why

系统内核型 entity type（node, dag, trigger, run-metadata）是 Entity 系统的骨架，被删除或篡改将导致运行时崩溃。当前 Web Console 对所有类型一视同仁地暴露编辑/删除操作，且 `GET /api/config/entity-types/{name}` 无法读取 `config/schemas/` 下的类型（返回 404），导致用户无法查看内核类型定义。

## What Changes

- `EntityTypeConfig` 新增 `system_protected: bool` 字段，默认 `false`
- 4 个内核 schema 文件（node, dag, trigger, run-metadata）标记 `system_protected: true`
- 后端 `GET /api/config/entity-types/{name}` 支持解析两个 schema 目录
- 后端 `PUT` / `DELETE` 对 `system_protected` 类型返回 403
- 前端类型卡片：`system_protected` 或 `name === 'relation'` 时隐藏删除按钮，编辑按钮改为查看（readonly 弹窗）
- 前端 list API 响应已包含 `system_protected` 字段，无需额外接口

## Capabilities

### New Capabilities
- `entity-type-protection`: 系统内核 entity type 的保护机制，覆盖 `system_protected` 字段声明、后端 403 拒绝和前端只读展示

### Modified Capabilities
- `entity-type-crud-api`: Read 端点需支持双目录解析；PUT/DELETE 端点需检查 `system_protected` 并拒绝

## Impact

- 后端: `src/stockimformation/config/schema.py`（模型）、`src/stockimformation/web/routes.py`（API）
- 前端: `frontend/src/features/entities/EntitiesPage.tsx`（类型卡片和弹窗）
- Schema 文件: `config/schemas/node.yaml`, `dag.yaml`, `trigger.yaml`, `run-metadata.yaml`
