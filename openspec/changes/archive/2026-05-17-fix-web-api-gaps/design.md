## Context

前端 `ConfigPage` 调用 `GET /api/config/portfolio` 和 `GET /api/config/system`，但后端仅有通用路由 `GET /api/config/{kind}/{name:path}`（需要两段路径参数）。前端 `NewFetcherSheet` 调用 `POST /api/graph/dag/{name}/nodes`，后端未实现。所有 mutation 缺少 `onError` 回调，API 失败时用户无反馈。

现有后端路由模式：
- `RuntimeConfigEditor.read(kind, name)` 返回 `EditableFile`（含 `content` 字段）
- 节点配置通过 `PUT /api/graph/node/{name}` 保存，但无"创建并加入 DAG"的组合操作

## Goals / Non-Goals

**Goals:**
- 前端配置页面能正确读取 portfolio 和 system 配置内容
- 前端创建 fetcher 节点后节点出现在 DAG 中
- API 错误时用户获得可见反馈
- 信息源页面在 API 失败时展示错误状态而非永久加载

**Non-Goals:**
- 不重构现有 `RuntimeConfigEditor` 架构
- 不引入全局 toast 组件库（使用 inline error 即可）
- 不改变现有 mutation 的成功路径行为

## Decisions

### D1: 后端新增专用 GET 路由 vs 前端修正路径

**选择**：后端新增 `GET /api/config/portfolio` 和 `GET /api/config/system`

**理由**：前端期望 `{ content: string }` 响应格式。现有通用路由 `GET /api/config/{kind}/{name}` 返回 `{ file: EditableFile }` 结构，且 portfolio 的 name 参数语义不明确（portfolio.yaml 只有一个文件）。新增专用路由更清晰，且与已有的 `PUT /api/config/portfolio` 对称。

**替代方案**：修改前端调用 `GET /api/config/portfolio/portfolio`——语义重复，不自然。

### D2: POST /api/graph/dag/{name}/nodes 实现策略

**选择**：组合操作——创建 node YAML 文件 + 将 node name 追加到 DAG 的 nodes 列表

**理由**：前端 `NewFetcherSheet` 期望一次调用完成"创建节点并加入 DAG"。拆成两次调用会增加前端复杂度且引入中间状态。

### D3: 错误反馈方式

**选择**：mutation `onError` 回调中使用 `window.alert()` 展示错误信息

**理由**：项目未引入 toast 库，alert 零依赖且足够传达错误。后续可替换为 toast 组件。

## Risks / Trade-offs

- [Risk] `POST /api/graph/dag/{name}/nodes` 创建的 node 文件名与已有 node 冲突 → 后端检查文件是否存在，冲突时返回 409
- [Risk] `GET /api/config/portfolio` 读取 YAML 返回原始文本，前端 textarea 直接展示 → 与现有 `PUT` 端点接受 JSON object 的行为不一致 → 保持 GET 返回原始 YAML 文本，PUT 保持现有 JSON object 语义不变
