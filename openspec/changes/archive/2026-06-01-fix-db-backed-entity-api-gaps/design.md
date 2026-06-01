## Context

数据库化核心实体迁移将 `node`/`dag`/`trigger`/`resource` 迁移到 DB，但 BFF/Web API 层保留旧的裸 list 返回格式，前端和后端之间存在响应结构契约不一致。同时 `GetHandler`/`SaveHandler` 仍使用硬编码文件路径，未利用 `bootstrap.handler_registry` 已有的 handler 注册信息。

## Decisions

1. Web BFF 层负责响应格式包装，不修改 gRPC 层返回格式
   gRPC `EntityService.List`/`Query` 保持 `EntityList` 原生返回，格式转换集中在 `routes.py`。避免修改 gRPC 契约影响其他客户端。

2. `_relation_filters` 返回 `dict | None` 区分「无关系查询」和「无条件关系查询」
   `type=relation` 无额外 filter 时返回空 dict（非 None），表示「查询全部关系」。`type=stock` 等非关系查询返回 `None` 跳过关系路径。

3. Handler 注册表驱动 handler 列表和读写
   `ListHandlers` 从 `bootstrap.handler_registry` 返回 handler 列表，`GetHandler`/`SaveHandler` 通过 registry 的 `HandlerEntry.path` 定位文件。handler 不再假设文件路径为 `extensions/{name}/handler.py`。

4. `entity-relations/types` 从 `attributes.relation_type` 提取类型
   真实的 `entity_search` 返回 `_entity_payload` 结构，`relation_type` 位于 `attributes` 内，非顶层字段。

## Risks

- [Response format change] → `/api/entities` 和 `/api/entity-relations` 从裸 list 变为对象包装。前端已按 `{entities: [...]}` 格式消费，本次修复对齐前端预期，无破坏性。
- [Handler 404 for shared handlers] → `ListHandlers` 只返回有独立 handler 文件的扩展条目，uzi-* 共享 `legacy-script-adapter` 的节点不出现在列表中。