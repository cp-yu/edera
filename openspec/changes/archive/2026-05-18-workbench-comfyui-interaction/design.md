## Context

当前 Workbench 画布基于 `@xyflow/react` + `@dagrejs/dagre`，节点使用固定 8 Handle（四边各 2 个）的 `CustomNode` 组件。交互质量远低于 ComfyUI/UE Blueprint 级别：连线视觉粗糙、Handle 位置固定死板、30+ 节点时布局混乱、拖拽位置不持久化、缺少基础编辑辅助（undo/redo、对齐、搜索添加）。

用户典型场景：30+ 节点的扇入/扇出 DAG，搭建一次后主要运行观察。节点类型差异大（fetcher/llm/aggregator），最终汇聚。

## Goals / Non-Goals

**Goals:**
- 达到 ComfyUI 级别的交互质量（用户手动排列节点 + 贝塞尔曲线视觉容错）
- 节点位置自动持久化，刷新不丢失布局
- 30+ 节点场景下的可用性（布局、分组、搜索、undo）
- 节点运行状态轻量可视化

**Non-Goals:**
- 不实现连线 waypoint 拖拽（依赖手动排列 + 贝塞尔容错）
- 不实现边缘任意点连接（保持 Handle-based 模型）
- 不改动后端 API（复用已有 `PUT /api/graph/dag/{name}`）
- 不引入非 React 渲染引擎（留在 ReactFlow 上）

## Decisions

### D1: 连线模型 — 动态 Handle + 贝塞尔曲线

**选择：** 按节点类型动态生成 Handle（左侧 input、右侧 output），数量由节点定义决定。连线使用 `smoothstep` 或 `bezier` 类型。

**替代方案：** 固定 8 Handle（当前方案）→ 对于端口语义不明确、连线方向混乱。

**理由：** ComfyUI 的端口模型就是"左 input 右 output，按类型排列"。ReactFlow 原生支持动态 Handle 生成，无需 hack。

### D2: 位置持久化 — localStorage 草稿 + debounce 写后端

**选择：** `onNodeDragStop` 时立即写 localStorage 作为草稿；debounce 500ms 后调用 `PUT /api/graph/dag/{name}` 将完整 UI + 拓扑写入后端。

**替代方案 A：** 仅手动保存按钮 → 用户忘记保存则丢失布局。
**替代方案 B：** 仅自动写后端 → 网络抖动时丢失。

**理由：** 混合策略兼顾即时性和可靠性。localStorage 保证即使网络断开也不丢失当前会话的布局。

### D3: 布局引擎 — ELK 替代 dagre

**选择：** 使用 `elkjs` 替代 `@dagrejs/dagre`，配置 `layered` 算法 + `DOWN` 方向。

**替代方案：** 保留 dagre → 不支持正交路由、分层效果差、扇入/扇出场景节点重叠。

**理由：** ELK 的 layered 算法专为 DAG 设计，支持端口约束、边路由优化、分层间距控制。对 30+ 节点的扇入/扇出拓扑效果显著优于 dagre。

### D4: 节点外观 — 按 type 差异化渲染

**选择：** 为每种节点类型（fetcher/llm/aggregator）设计独立的视觉样式（颜色、尺寸），未识别类型回退到中性样式，通过 `CustomNode` 内按 type 分支渲染。

**理由：** 30+ 节点时，类型差异化是快速定位的关键。ComfyUI 每种节点类型都有独特的颜色标识。

### D5: 右键菜单 — 原生 Context Menu

**选择：** 使用 ReactFlow 的 `onNodeContextMenu` / `onEdgeContextMenu` + 自定义浮层实现右键菜单。Edge 菜单包含"反转方向"和"删除"操作。

**理由：** 反转方向是纠错快捷操作（删旧边建新边，source/target 互换），比删除重连效率高。

### D6: Undo/Redo — 基于 state snapshot 栈

**选择：** 维护 `{nodes, edges}` 的 snapshot 栈（最多 50 步），Ctrl+Z / Ctrl+Shift+Z 触发。

**替代方案：** 基于 command pattern 的细粒度 undo → 实现复杂度高，收益有限。

**理由：** 对于"搭建一次"的场景，粗粒度 snapshot 足够。50 步上限控制内存。

### D7: 节点分组 — 按 target 自动推导视觉分区

**选择：** 根据节点关联的 target 自动计算分组，在画布上用半透明背景色块包围同组节点。不持久化分组信息。

**理由：** 分组是视觉辅助而非数据模型，按 target 推导即可，无需用户手动管理。

### D8: 搜索添加节点 — Cmd+K 弹窗

**选择：** 全局快捷键 Cmd+K 打开搜索面板，模糊匹配节点原型名称，选中后在画布中心添加。

**理由：** 30+ 节点时从 Palette 拖拽效率低。ComfyUI 的双击空白区域弹出搜索是核心交互。

### D9: 对齐辅助线 + Snap to Grid

**选择：** 使用 ReactFlow 的 `snapToGrid` prop + 自定义对齐辅助线（节点拖拽时显示与相邻节点的对齐参考线）。

**理由：** 手动排列节点的前提是有对齐辅助，否则 30+ 节点无法排整齐。

## Risks / Trade-offs

- **ELK bundle 体积** → elkjs wasm 约 200KB gzip，对于桌面工具可接受。若体积敏感可用 web worker 异步加载。
- **自动保存冲突** → 多标签页同时编辑同一 DAG 可能覆盖。当前为单用户本机工具，风险极低。
- **Undo 栈内存** → 50 步 × 30 节点的 snapshot 约 100KB，可忽略。
- **ELK 布局性能** → 30-50 节点的 layered 布局 < 100ms，不阻塞 UI。超过 100 节点需考虑 web worker。
