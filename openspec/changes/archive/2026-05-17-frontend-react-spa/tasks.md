## 1. Actions

- [x] A1 初始化 `frontend/` 项目：`npm create vite@latest frontend -- --template react-ts`
- [x] A2 安装核心依赖：`@xyflow/react`, `@tanstack/react-query`, `zustand`, `react-router-dom`
- [x] A3 配置 Tailwind CSS + `tailwind.config.ts`（design tokens: colors, fonts, spacing）
- [x] A4 初始化 shadcn/ui：`npx shadcn@latest init` + 安装基础组件（Button, Select, Dialog, Sheet, AlertDialog, Badge, Input, Textarea, Tabs, Toast）
- [x] A5 创建 `src/api/client.ts`：fetch wrapper，base URL 从环境变量读取，统一错误处理
- [x] A6 创建 `src/api/types.ts`：所有 API 响应/请求的 TypeScript 接口定义
- [x] A7 创建 TanStack Query hooks：`useDag`, `useNodePrototypes`, `useRuntimeStatus`, `useDagStatus`, `useResults`, `useAdvices`, `useBriefings`, `useSourcesHealth`
- [x] A8 创建 mutation hooks：`useSaveDag`, `useSaveNode`, `useRunDag`, `useStopDag`, `useCreateNode`, `useCreateSource`
- [x] A9 创建 `src/store/useAppStore.ts`：Zustand store（selectedDagName, selectedNodeId, targetFilter, theme）
- [x] A10 创建 `src/router/index.tsx`：React Router v6 路由定义（/, /workbench, /results, /results/advices/:id, /results/briefings/:id, /sources, /config）
- [x] A11 创建 `src/components/layout/AppShell.tsx`：应用外壳（侧边栏导航 + 主内容区）
- [x] A12 创建 `src/components/layout/SideNav.tsx`：侧边栏导航组件（工作台、结果、信息源、配置）
- [x] A13 实现主题切换：dark class toggle + localStorage 持久化
- [x] A14 创建 `src/features/workbench/WorkbenchPage.tsx`：工作台页面容器（三栏布局）
- [x] A15 创建 `src/features/workbench/components/Palette.tsx`：节点面板（分组列表 + 拖拽源 + "+ New Fetcher"按钮）
- [x] A16 创建 `src/features/workbench/components/Canvas.tsx`：React Flow 画布封装（useNodesState, useEdgesState, onConnect, onDrop）
- [x] A17 创建 `src/features/workbench/components/nodes/CustomNode.tsx`：自定义节点组件（target 颜色边框、状态指示、handles）
- [x] A18 创建 `src/features/workbench/components/Inspector.tsx`：节点配置面板（表单 + 可编辑/只读字段 + 保存按钮 + 全局警告 AlertDialog）
- [x] A19 创建 `src/features/workbench/components/BottomToolbar.tsx`：底部工具栏（DAG 选择器 + Run/Stop + 状态 Badge + Target 过滤）
- [x] A20 创建 `src/features/workbench/components/TargetFilter.tsx`：Target 多选过滤器
- [x] A21 创建 `src/features/workbench/components/NewFetcherSheet.tsx`：新建 Fetcher 滑出面板
- [x] A22 创建 `src/features/workbench/components/NewSourceDialog.tsx`：内联创建信息源对话框
- [x] A23 实现节点颜色逻辑：`src/lib/colors.ts`（target 色板、RGB 均值计算、亮度校正）
- [x] A24 实现运行状态轮询：DAG 运行时启用 `refetchInterval: 2000`，完成后停止
- [x] A25 实现节点运行状态可视化：running=pulse 动画, succeeded=绿色, failed=红色边框
- [x] A26 创建 `src/features/results/ResultsPage.tsx`：结果浏览页（摘要卡片 + 简报 + 建议表 + 事件表）
- [x] A27 创建 `src/features/results/AdviceDetail.tsx`：建议详情页
- [x] A28 创建 `src/features/results/BriefingDetail.tsx`：简报详情页
- [x] A29 创建 `src/features/sources/SourcesPage.tsx`：信息源健康监控页
- [x] A30 创建 `src/features/config/ConfigPage.tsx`：高级配置页（portfolio JSON 编辑 + system 配置）
- [x] A31 创建 `nginx.conf` 模板：SPA static files + API proxy_pass
- [x] A32 配置 `vite.config.ts`：API proxy（开发环境）、build output 路径

## 2. Checks

- [x] C1 项目构建通过
  - Covers: A1, A2, A3, A4
  - Command: `cd frontend && npm run build`
  - Expect: 构建成功，无 TypeScript 错误，产出 `dist/` 目录

- [x] C2 路由导航正常
  - Covers: A10, A11, A12
  - Command: `cd frontend && npm run dev` 后浏览器访问各路由
  - Expect: 所有路由正确渲染对应页面，侧边栏导航高亮正确

- [x] C3 DAG Workbench 三栏布局渲染
  - Covers: A14, A15, A16, A18, A19
  - Command: 浏览器访问 `/workbench`
  - Expect: 三栏布局正确渲染，Palette 展示节点列表，Canvas 展示 React Flow 画布，Inspector 展示空状态

- [x] C4 节点选择和 Inspector 编辑
  - Covers: A17, A18
  - Command: 在画布上点击节点
  - Expect: Inspector 展示节点配置，可编辑字段可修改，只读字段不可编辑

- [x] C5 DAG 切换刷新
  - Covers: A19, A7
  - Command: 在底部工具栏切换 DAG
  - Expect: 画布重新渲染新 DAG 的拓扑，Inspector 清空，状态更新

- [x] C6 节点保存全局警告
  - Covers: A18
  - Command: 修改节点参数后点击保存
  - Expect: 弹出 AlertDialog 警告全局影响，确认后调用 PUT API

- [x] C7 Target 过滤 opacity
  - Covers: A20, A23
  - Command: 选择特定 target 过滤
  - Expect: 非匹配节点 opacity 降至 0.2，匹配节点保持 1.0

- [x] C8 运行控制和状态轮询
  - Covers: A19, A24, A25
  - Command: 点击"运行"按钮
  - Expect: 状态变为 running，节点显示 pulse 动画，完成后 toast 通知

- [x] C9 主题切换
  - Covers: A13
  - Command: 点击主题切换按钮
  - Expect: UI 立即切换暗色/亮色，刷新后保持选择

- [x] C10 结果页面数据展示
  - Covers: A26, A27, A28
  - Command: 浏览器访问 `/results`
  - Expect: 摘要卡片、简报、建议表正确渲染 API 数据
