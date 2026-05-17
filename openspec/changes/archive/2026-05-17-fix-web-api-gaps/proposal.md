## Why

前端调用了多个后端未实现的 API endpoint，导致信息源健康度页面永远显示"加载中..."、新增 fetcher 点击创建无反应、设置页面 Portfolio/System 配置内容为空。同时，mutation 缺少错误处理使得运行按钮点击后无任何反馈。

## What Changes

- 后端新增 `GET /api/config/portfolio` 和 `GET /api/config/system` endpoint，返回配置文件原始内容
- 后端新增 `POST /api/graph/dag/{name}/nodes` endpoint，支持向 DAG 添加新节点
- 前端为 `useRunDag`、`useCreateNode` 等 mutation 添加错误反馈（toast 或 inline error）
- 前端 `SourcesPage` 添加 error state 展示，避免永远停留在"加载中..."

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `runtime-config-editing`: 新增 `GET /api/config/portfolio` 和 `GET /api/config/system` 读取端点，满足前端配置页面读取需求
- `node-graph-dag-editor`: 新增 `POST /api/graph/dag/{name}/nodes` 端点，支持从 UI 创建节点
- `sources-monitor-ui`: 添加 API 错误状态展示，避免无限加载

## Impact

- 后端 `src/stockimformation/web/routes.py`：新增 3 个路由
- 前端 `src/api/mutations.ts`：添加 onError 回调
- 前端 `src/features/sources/SourcesPage.tsx`：添加 error 分支
- 前端 `src/features/config/ConfigPage.tsx`：修正 API 路径或后端适配
