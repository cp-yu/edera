## Context

当前 workbench 画布基于 `@xyflow/react`（ReactFlow），需要从零拼装连线路由、端口吸附、框选等交互，开发成本高且交互质量不达标。此前尝试过 LiteGraph.js 原版但因找不到开箱即用的模板而放弃。

ComfyUI Frontend monorepo 中维护了一个 TypeScript 版 litegraph（`src/lib/litegraph/`），自包含、无外部依赖、交互质量达到 ComfyUI 级别。该仓库已归档，代码稳定，适合 vendor 进项目。

现有架构：Vite + React + zustand + TanStack Query。三栏布局（Palette | Canvas | Inspector）+ 底部工具栏。

## Goals / Non-Goals

**Goals:**
- 用 ComfyUI litegraph fork 替换 ReactFlow，获得开箱即用的 node editor 交互
- 保留现有 React Palette、Inspector、BottomToolbar 组件不变
- 建立双向 adapter 实现后端 DAG 格式与 LGraph 格式互转
- 手动保存 + localStorage 草稿机制
- CSS 换皮达到深色主题现代视觉

**Non-Goals:**
- 不做节点内嵌控件（配置编辑全在 Inspector）
- 不跟 ComfyUI 上游同步（已归档）
- 不改后端 DAG API 和 yaml 格式
- 不改 Inspector/Palette 的业务逻辑
- 不引入 jQuery/D3 等额外运行时依赖

## Decisions

### D1: 画布引擎选择 — ComfyUI litegraph fork（vendor）

**选择**：从 `Comfy-Org/ComfyUI_frontend` 的 `src/lib/litegraph/` 目录拷贝 TypeScript 源码到 `frontend/src/lib/litegraph/`。

**替代方案**：
- Node-RED editor：交互完整但依赖 jQuery + D3 + RED 全局对象，剥离成本高
- Rete.js v2：框架无关但交互质量不如 litegraph
- 原版 litegraph.js：长期无维护

**理由**：litegraph fork 自包含无依赖、TypeScript、交互质量即 ComfyUI 级别、代码量可控（~15k 行）。

### D2: 集成方式 — 直接嵌入 React 项目

**选择**：LiteGraph canvas 作为 React 组件内的 `<canvas>` 元素挂载，通过 ref 管理生命周期。

**理由**：需要与 React 侧边栏（Palette/Inspector）直接通信，iframe 隔离会增加消息桥接复杂度。

### D3: 数据流 — 后端为 source of truth + 双向 adapter

**选择**：
```
加载：API → DAG JSON → adapter.tograph() → LGraph
保存：LGraph → adapter.toDag() → API → yaml
```

**理由**：后端 DAG yaml 承担执行语义，前端只是编辑视图。adapter 层隔离两种数据模型，未来换引擎成本低。

### D4: 节点注册 — 统一 DynamicNode class + 动态 ports

**选择**：一个 `DynamicNode` 基类，API 返回节点原型后遍历注册。通过构造参数决定 title/color/ports 数量。

**理由**：节点类型从后端动态获取，不适合编译时静态注册。统一 class 保持 adapter 最薄，颜色区分类型即可。保留继承扩展空间。

### D5: 保存策略 — 手动保存 + localStorage 草稿

**选择**：
- 用户点击"保存"时一次性 dump LGraph → adapter → API
- 每 60s 自动将 LGraph 状态序列化到 `localStorage['dag-draft:${dagName}']`
- 草稿间隔和开关可配置

**理由**：LiteGraph 操作频率高，操作即保存会频繁触发后端校验。手动保存给用户试错空间。

### D6: 事件桥接 — LiteGraph 回调 → zustand

**选择**：
- `LGraphCanvas.onNodeSelected` → `useAppStore.setSelectedNode`
- `LGraph.onNodeAdded` / `onNodeRemoved` → 同步 DAG 草稿状态
- `LGraph.onConnectionChange` → 同步 edges 状态
- Palette 拖拽 → 调用 `LGraph.add(new DynamicNode(...))`

**理由**：LiteGraph 有完整的回调 API，无需 monkey-patch。zustand 作为中间层让 Inspector/Palette 保持响应式。

### D7: UI 美化 — CSS 换皮

**选择**：覆盖 litegraph 默认样式变量（背景色、节点色、字体、圆角），匹配现有 Tailwind 深色主题。不改渲染逻辑。

**理由**：浅 fork 策略，样式层改动不影响交互逻辑稳定性。

## Risks / Trade-offs

- **[vendor 代码维护]** → litegraph fork 已归档无上游更新，bug 需自行修复。缓解：代码量可控（~15k 行 TS），且 ComfyUI 已验证稳定性。
- **[Canvas 与 React 状态同步]** → LiteGraph 内部状态和 zustand 可能不一致。缓解：单向数据流（后端 → LGraph → 事件 → zustand），不做双向绑定。
- **[Palette 拖拽跨框架]** → React 组件拖拽到 canvas 元素需要处理 HTML5 DnD 事件。缓解：现有 `onDragStart` 逻辑可复用，drop 目标改为 canvas 的 dragover/drop 事件。
- **[草稿丢失]** → localStorage 有容量限制且换设备丢失。缓解：单人工具项目，可接受；未来可加后端 draft API。
