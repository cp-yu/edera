## Context

节点管理页面（`NodesPage.tsx`）当前使用统一的 `JsonCard` 组件渲染所有节点类型，以 JSON textarea 作为唯一编辑方式。Function 节点的 handler 代码存储在独立 `.py` 文件中（`handlers/{name}.py`），后端已提供 `GET/PUT /api/graph/handlers/{name}` API，但前端从未调用——`withNodeCodeFields()` 仅返回空字符串 `handler_code: ''`。

Workbench Inspector 的 `PermissionConfigurator` 接收 `dag.entity_types`（所有 entity type），遍历全部 type 展示权限字段。节点通过 `EntitySelector` 已选择了具体 entities（如 `["stock:AAPL"]`），但权限配置器未利用此信息做过滤。

## Goals / Non-Goals

**Goals:**
- 节点管理页面提供顶层 Handler tab，从后端加载 Function 节点 handler 代码并支持保存
- PermissionConfigurator 仅展示节点已选 entities 对应的 entity type 的权限字段
- 保持现有 LLM 节点和 Skills 的编辑体验不变

**Non-Goals:**
- 不引入 Monaco/CodeMirror 等重量级编辑器（monospace textarea 足够）
- 不改变后端 API 或存储结构
- 不重构 LLM 节点的 system_prompt 编辑方式（后续可独立处理）

## Decisions

### D1: 节点管理页新增顶层 Handler tab

在 `LLM 节点`、`Function 节点`、`Skills` 同级新增 `Handler` tab：
- **Function 节点 tab**：继续使用 JSON 编辑（排除 `handler_code` 字段），保持卡片结构不变
- **Handler tab**：按 Function 节点列出 handler 代码编辑卡片，monospace textarea 通过 `useQuery` 调用 `GET /api/graph/handlers/{name}` 加载代码，保存时调用 `PUT`

**理由**：handler 代码是独立文件，需要独立的页面级编辑入口；顶层 tab 与节点类型管理 tab 同级，避免把代码编辑塞进每个 Function 节点卡片内部。

**备选方案**：在 JSON 中内联 handler_code 字段 → 拒绝，因为代码量大时 JSON 编辑器体验极差，且与后端存储模型不一致。

### D2: 新增 `useHandler` query hook

在 `frontend/src/api/queries.ts` 新增：
```typescript
export function useHandler(name: string | null) {
  return useQuery({
    queryKey: ['handler', name],
    queryFn: () => apiFetch<{ name: string; code: string }>(`/api/graph/handlers/${name}`),
    enabled: !!name,
  })
}
```

对应 mutation 在 `mutations.ts` 新增 `useSaveHandler`。

### D3: PermissionConfigurator 按已选 entities 过滤

从 `formValues.entities`（`string[]`，格式 `"type:id"`）提取 type 前缀集合，过滤 `entityTypes` 后传入 `PermissionConfigurator`。

```typescript
const selectedTypes = new Set(
  (Array.isArray(formValues.entities) ? formValues.entities : [])
    .map((ref: string) => ref.split(':')[0])
)
const filteredEntityTypes = Object.fromEntries(
  Object.entries(dag.entity_types ?? {}).filter(([type]) => selectedTypes.has(type))
)
```

**理由**：逻辑简单，无需后端变更，过滤在渲染层完成。当 entities 为空时，PermissionConfigurator 不展示任何 type（符合语义：没选实体就没有权限可配）。

### D4: entities 变更时清理失效的 permission overrides

当用户取消选择某个 entity 导致其 type 不再被引用时，自动清除该 type 的 permission overrides。避免保存时携带无效配置。

## Risks / Trade-offs

- [Handler 加载延迟] → Handler tab 中显示 loading 状态，useQuery 缓存避免重复请求
- [entities 变更导致 permissions 丢失] → 仅清理不再引用的 type，用户重新选择同 type 的 entity 时 permissions 需重新配置。可接受，因为这是用户主动操作
