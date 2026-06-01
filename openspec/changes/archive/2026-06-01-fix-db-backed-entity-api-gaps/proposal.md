## Why

[问题描述] 数据库化核心实体迁移后暴露多个 API 契约与查询路由不一致：
- `/api/entities`、`/api/entity-relations`、`/api/entity-relations/types` 返回裸 list 而非前端期望的 `{entities: [...]}` / `{relations: [...]}` / `{types: [...]}` 结构
- entity payload 缺少 `display` 字段，前端实例标签空白
- `type=relation` 查询因 `_relation_filters` 返回空 dict（falsy）跳过关系查询路径
- entity-relations 响应未转换为前端 `{id, entities, type, metadata}` 结构
- `GetHandler`/`SaveHandler` 按 handler name 硬编码拼路径，无法匹配扩展目录实际命名
- handlers tab 缺少 handler 列表 API，前端遍历 node 列表间接查询
- `entity-relations/types` 路由中 `relation_type` 取值路径错误（顶层 vs `attributes.relation_type`）

## What Changes

- `routes.py`: `/api/entities`、`/api/entity-relations`、`/api/entity-relations/types` 包装为 `{entities}`/`{relations}`/`{types}` 格式；relation 响应转换为前端 Relation 结构
- `server.py` `_entity_payload`: 增加 `display` 字段（`render_entity_display` 按 entity_type display_template 渲染）
- `server.py` `_relation_filters`: 返回 `dict | None`，`type=relation` 时返回非 None 空 dict 以正确路由到 `_query_relations`
- `routes.py` `entity-relations/types`: 从 `attributes.relation_type` 取值
- `graph_service.py`: 新增 `ListHandlers` RPC，回 handler_registry 列表；`GetHandler`/`SaveHandler` 改用 `bootstrap.handler_registry` 查找路径
- `profis/edera.proto`: GraphService 新增 `ListHandlers` RPC
- `grpc_client.py`: 新增 `graph_list_handlers` 方法
- `NodesPage.tsx`: handlers tab 由 `useHandlers` hook 驱动，`HandlerCard` 以 handler name 为 key
- `queries.ts`: 新增 `useHandlers` hook 调用 `/api/graph/handlers`

## Capabilities

### Modified Capabilities
- `entity-instance-crud-api`: 响应包装为 `{entities: [...]}`，entity 含 `display` 字段
- `entity-relation-crud-api`: 响应包装 + 查询路由修复 + relation_type 字段路径修复
- `grpc-graph-service`: Handler 注册表驱动的 ListHandlers/GetHandler/SaveHandler

## Impact

- 影响 `packages/core/src/edera_core/web/routes.py`、`server.py`、`graph_service.py`、`grpc_client.py`
- 影响 `proto/edera.proto`、`packages/core/src/edera_core/proto/edera_pb2_grpc.py`
- 影响 `apps/web-console/src/features/nodes/NodesPage.tsx`、`src/api/queries.ts`
- 新增测试覆盖所有修复点