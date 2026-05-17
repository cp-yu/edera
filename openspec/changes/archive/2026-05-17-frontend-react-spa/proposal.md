## Why

当前 Web 控制台基于 Jinja2 SSR + 手写 CSS + LiteGraph.js，交互能力有限、视觉陈旧、无法支撑 DAG Workbench 统一工作台的复杂交互需求（拖拽、实时状态、内联编辑）。需要迁移到现代 React SPA 以实现专业级金融工具体验。

## What Changes

- 新建 `frontend/` 目录，基于 Vite + React 18 + TypeScript 构建全新 SPA
- 引入 React Flow 替代 LiteGraph.js 作为 DAG 画布渲染引擎
- 引入 shadcn/ui + Tailwind CSS 作为设计系统
- 引入 TanStack Query 管理服务端状态缓存
- 引入 Zustand 管理客户端 UI 状态
- 实现 DAG Workbench 统一工作台（三栏布局：Palette | Canvas | Inspector + 底部工具栏）
- 实现结果浏览页（摘要卡片 + 简报 + 建议表）
- 实现信息源健康监控页
- 实现高级配置页（portfolio/system YAML 编辑）
- 支持暗色/亮色主题切换
- 生产环境通过 nginx 托管静态文件

## Capabilities

### New Capabilities

- `dag-workbench-ui`: DAG 统一工作台前端，覆盖三栏布局、React Flow 画布、节点 Palette、Inspector 编辑面板、底部工具栏、Target 过滤、节点颜色映射、内联创建和全局保存警告
- `spa-shell`: SPA 应用外壳，覆盖路由、导航、主题切换、API 客户端层和全局状态管理
- `results-dashboard-ui`: 结果浏览前端，覆盖摘要卡片、简报展示、建议表格、事件表格和筛选功能
- `sources-monitor-ui`: 信息源健康监控前端，覆盖健康状态卡片和执行日志展示

### Modified Capabilities

（无 — 前端为全新实现，不修改现有后端 spec 行为）

## Impact

- 新增 `frontend/` 目录（约 50+ 文件）
- 新增 `nginx.conf` 配置模板
- 依赖新增：react, react-dom, @xyflow/react, @tanstack/react-query, zustand, tailwindcss, vite 等
- 后端依赖：需要 `backend-per-dag-api` change 先完成（提供 per-DAG API）
- 部署变更：nginx 反向代理配置
