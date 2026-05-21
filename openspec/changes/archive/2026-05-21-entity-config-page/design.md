## Context

当前系统已完成从 portfolio 到 entity 的数据迁移：`entities.yaml` + `entity-relations.yaml` 存储所有实体和关系，`schemas/entity-types/*.yaml` 定义类型 schema。但 UI 层仍停留在旧模式 — ConfigPage 展示已废弃的 Portfolio JSON 编辑器，entity 管理只能通过手动编辑 YAML 文件完成。Pipeline services 通过 `PortfolioConfig` 兼容层（`EntitiesConfig.to_portfolio()`）间接访问实体数据。

## Goals / Non-Goals

**Goals:**
- 提供完整的 Entity 管理 UI（类型/实例/关系 CRUD）
- 清除所有 portfolio 遗留代码和文件
- Pipeline services 直接使用 `EntityStore`，消除兼容层
- 保持与现有 entity 系统行为的完全兼容

**Non-Goals:**
- 不改变 entity type schema 的语义（JSON Schema 子集）
- 不引入实体版本历史或审计日志
- 不改变节点执行时的权限检查逻辑
- 不重构 `EntityStore` 内部实现

## Decisions

### D1: Entity Type CRUD API 路径

**选择**: `GET/POST /api/config/entity-types`, `GET/PUT/DELETE /api/config/entity-types/{name}`

**替代方案**: 复用现有 `/api/config/{kind}/{name}` 通用路径 — 拒绝，因为 entity type 文件在 `schemas/entity-types/` 而非 `config/` 目录，语义不同。

### D2: 单实例 CRUD 复用 EntityStore

**选择**: 新增 `POST /api/entities`、`PUT /api/entities/{id}`、`DELETE /api/entities/{id}`，内部调用 `EntityStore.create()`/`save()`。

**替代方案**: 继续用整体保存 `POST /api/config/entities` — 拒绝，因为并发编辑有覆盖风险，且 EntityStore 已有单实例逻辑。

### D3: 关系加 UUID ID

**选择**: `EntityRelationConfig` 增加 `id: str` 字段（默认 `uuid4().hex`），加载时自动补全缺失 ID。API: `POST /api/entity-relations`、`DELETE /api/entity-relations/{id}`。

**替代方案**: 用组合键（entities + type）定位 — 拒绝，因为数组顺序敏感性导致匹配歧义。

### D4: 类型删除 cascade 参数

**选择**: `DELETE /api/config/entity-types/{name}?cascade=true` — 默认拒绝删除（有实例时返回 409），cascade=true 时先删实例和相关关系再删类型。

**替代方案**: 前端分步调用（先删实例再删类型）— 拒绝，因为非原子操作可能中途失败留下不一致状态。

### D5: Pipeline services 重构策略

**选择**: services 接收 `EntityStore` 实例，通过 `entities.entities` 按 type 过滤获取所需数据。

**替代方案**: 保留 TargetConfig/SourceConfig 作为 DTO — 拒绝，因为只是换名的兼容层，没有真正解耦。

### D6: 前端 schema-driven 表单

**选择**: 混合策略 — 有 `properties` 定义的 object 递归渲染子表单；无定义的 fallback 到 JSON 文本输入。`field_permissions` 中 `read-only` 字段渲染为 disabled input。

### D7: 关系类型输入

**选择**: Combobox 模式 — 从现有 relations 中提取已用过的 type 作为建议列表，同时允许自由输入新类型。

## Risks / Trade-offs

- **[Breaking change]** 删除 `PortfolioConfig` 影响 pipeline.py 和 3 个 service 模块 → 通过测试覆盖确保行为不变；重构后 services 直接从 EntityStore 获取等价数据
- **[entity-relations.yaml 格式变更]** 增加 `id` 字段 → 加载时自动补全，向后兼容无 ID 的旧格式
- **[cascade 删除原子性]** 类型+实例+关系需要一次性完成 → 在内存中完成所有变更后统一 persist，任一步骤失败则全部回滚
- **[Schema-driven 表单局限]** 复杂 JSON Schema 特性（allOf、oneOf、$ref）不支持 → 第一版只处理 `type`、`required`、`properties`，覆盖当前所有 entity type 的实际 schema

## Migration Plan

1. 后端先增加新 API endpoints（entity type CRUD、单实例 CRUD、单关系 CRUD）
2. 重构 pipeline services 使用 EntityStore（此时 PortfolioConfig 仍存在但无调用方）
3. 删除 PortfolioConfig 及相关代码和 portfolio.yaml
4. 前端新增 EntitiesPage，修改路由和侧边栏
5. 前端 ConfigPage 删除 Portfolio tab，简化为 System 编辑器
6. 回滚策略：git revert 整个 change（单次提交或 squash merge）
