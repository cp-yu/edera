## Context

Entity 系统有两个 schema 目录：`schemas/entity-types/`（用户业务型）和 `config/schemas/`（系统型）。当前 Web Console 的 entity type CRUD API 仅解析前者路径，导致系统内核类型（node, dag, trigger, run-metadata）无法被读取。同时 API 对所有类型无差别暴露 PUT/DELETE，存在误操作风险。

## Goals / Non-Goals

**Goals:**
- 内核类型可查看、不可编辑/删除（后端 403 强制）
- 前端对 `system_protected` 类型和 `relation` 类型隐藏危险操作
- `GET /api/config/entity-types/{name}` 能读取两个目录下的类型

**Non-Goals:**
- 不引入角色/权限系统，保护机制仅基于 schema 自声明
- 不改变 `load_entity_type_configs` 的加载逻辑
- 不保护 relation 的后端操作

## Decisions

### D1: `system_protected` 作为 schema 字段自声明

在 `EntityTypeConfig` 新增 `system_protected: bool = False`。由 YAML 文件自行声明。

**理由**: 最简单的实现路径，无需 loader 层面的路径判断逻辑。声明在文件中，语义清晰。

**替代方案**: 按文件来源路径自动标记 — 更安全但耦合了目录结构语义，且无法精确控制（`config/schemas/` 下的 advice/briefing 等不需要保护）。

### D2: 路径解析策略 — 双目录 fallback

`_entity_type_path` 改为 `_resolve_entity_type_path`，先查 `schemas/entity-types/{name}.yaml`，再查 `config/schemas/{name}.yaml`。仅用于 GET 读取。PUT/DELETE 仍只操作 `schemas/entity-types/`，对 protected 类型直接 403。

**理由**: GET 需要能读到所有类型；写操作限制在用户目录，protected 类型的写操作在检查 `system_protected` 时就已被拦截。

### D3: 前端 relation 保护 — 硬编码条件

前端保护条件: `type.system_protected || name === 'relation'`。

**理由**: 单一特例，不值得引入新字段。relation 是前端依赖的辅助类型，但后端不需要强制保护。

## Risks / Trade-offs

- [用户可手动编辑 YAML 移除 `system_protected: true`] → 可接受，本机工具面向开发者，Web Console 保护足够
- [前端硬编码 `relation`] → 如果未来有更多类似需求，需重构为字段驱动。当前单一特例不值得过度设计
