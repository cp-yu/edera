## Why

节点管理页面的 Function 节点 handler 编辑体验缺失——当前实现仅在 JSON textarea 中放置空的 `handler_code` 字段，未调用后端 handler API 加载实际代码。同时，Workbench Inspector 的权限配置器展示了所有 entity type 的字段，而非仅展示当前节点已选择的 entity 对应的 type，造成信息噪音。

## What Changes

- 节点管理页面新增顶层 Handler tab，与 LLM 节点、Function 节点和 Skills tab 同级，用于编辑 Function 节点 handler 代码
- Workbench Inspector 的 `PermissionConfigurator` 根据节点已选 entities 过滤，仅展示相关 entity type 的权限字段

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `node-management-page`: 节点管理页新增顶层 Handler tab，集中编辑 Function 节点 handler 代码
- `dag-workbench-ui`: Inspector 权限配置器按节点已选 entities 过滤展示的 entity type

## Impact

- 前端 `frontend/src/features/nodes/NodesPage.tsx` — 新增顶层 Handler tab
- 前端 `frontend/src/features/workbench/components/Inspector.tsx` — PermissionConfigurator 增加过滤逻辑
- 前端 API 层 — 可能需要新增 handler 读取 query hook（`GET /api/graph/handlers/{name}`）
- 后端无变更（API 已存在）
