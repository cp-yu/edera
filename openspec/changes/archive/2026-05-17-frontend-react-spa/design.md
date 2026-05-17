## Context

后端正在重构为纯 API 服务器（`backend-per-dag-api` change），前端需要独立的 SPA 应用对接 REST API。

参考规格文档：`docs/dag-page-capabilities.md`（DAG 页面能力定义）。

当前前端技术栈（将被完全替换）：
- Jinja2 模板 + 手写 CSS（650 行）
- LiteGraph.js（节点图编辑器）
- 原生 JS（dag_editor.js, node_graph_editor.js）

## Goals / Non-Goals

**Goals:**

- 实现 DAG Workbench 统一工作台（IDE 风格三栏固定布局）
- 使用 React Flow 提供专业级节点图编辑体验
- 使用 shadcn/ui + Tailwind 建立一致的设计系统
- 支持暗色/亮色主题
- 桌面优先但响应式
- 通过 TanStack Query 实现高效的服务端状态管理和轮询

**Non-Goals:**

- 不实现移动端完整体验（工作台页面仅桌面端）
- 不实现 WebSocket 实时推送（使用 HTTP 轮询）
- 不实现用户认证/多用户（保持单用户本地工具定位）
- 不实现国际化（仅中文 UI）

## Decisions

### Decision 1: IDE 工作台布局（而非浮动面板）

**选择**：固定三栏布局（Palette 250px | Canvas 1fr | Inspector 300px + Bottom 40px）

**替代方案**：全屏画布 + 浮动面板（类 Figma）

**理由**：
- 金融工具用户需要频繁编辑节点参数，固定 Inspector 减少交互摩擦
- 信息密度高，所有工具触手可及
- 符合数据管道工具（Airflow/dbt）的用户心智模型

### Decision 2: React Flow（而非继续用 LiteGraph）

**选择**：`@xyflow/react`（React Flow v12+）

**替代方案**：继续封装 LiteGraph.js

**理由**：
- React 生态原生集成，自定义节点组件用 JSX 编写
- 内置 minimap、controls、background 等功能
- 社区活跃，文档完善
- LiteGraph 定制性有限且样式老旧

### Decision 3: Zustand（而非 Redux/Context）

**选择**：Zustand 管理客户端 UI 状态

**替代方案**：Redux Toolkit 或 React Context

**理由**：
- 状态量小（selectedDag, selectedNode, theme, targetFilter）
- Zustand API 极简，无 boilerplate
- 与 TanStack Query 互补（Query 管服务端状态，Zustand 管 UI 状态）

### Decision 4: 节点过滤用 opacity（而非隐藏）

**选择**：非匹配节点 opacity 降至 0.2，保留在画布上

**替代方案**：完全隐藏非匹配节点

**理由**：
- 保留整体拓扑上下文，用户不会迷失方向
- 视觉上清晰区分"关注"和"背景"
- React Flow 的 `style` prop 直接支持

### Decision 5: 节点颜色策略

**选择**：
- 单 target → 该 target 的预定义颜色
- 多 target → RGB 均值 + 多色边框
- 预定义 8-10 色 palette，确保可区分性

**风险缓解**：对 RGB 均值结果做亮度/饱和度校正，避免"泥巴色"

## Risks / Trade-offs

- **[风险] React Flow 性能** → 当前 DAG 节点数 < 20，不构成问题。若未来超过 100 节点，需启用虚拟化。

- **[风险] 首次加载体积** → React + React Flow + shadcn/ui bundle 约 200-300KB gzipped。对本地工具可接受。可通过路由级 code splitting 优化。

- **[Trade-off] 开发成本** → 全新前端开发量大（约 50+ 文件）。但长期维护性和扩展性远优于 Jinja2 模板。

- **[风险] API 兼容性** → 前端依赖 `backend-per-dag-api` change 提供的新 API。需确保两个 change 协调推进。
