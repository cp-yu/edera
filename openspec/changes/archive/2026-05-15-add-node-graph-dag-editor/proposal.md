## Why

当前 DAG 编辑仍然停留在配置表单和 YAML 兜底层面，无法满足类似 ComfyUI 的节点图编排体验：用户不能在画布上拖拽节点、通过端口连线表达数据流、在侧边栏编辑节点配置，也不能直接在图上观察节点运行状态。项目需要把 DAG 编辑从“配置文件维护”升级为“Node Graph 编排界面”，但仍保持本机 Web 控制台和现有后端校验作为边界。

## What Changes

- 新增 ComfyUI 风格的 Node Graph DAG 编辑界面，作为 DAG 编辑的主入口，取代轻量表格作为主要交互。
- 在画布中展示节点、输入/输出端口、连线数据流类型、fan flags 和节点运行状态。
- 支持节点拖拽定位、从节点 palette 添加节点、端口连线、删除节点/连线，并保存回现有 DAG 配置。
- 新增右侧 Inspector，选中节点后展示并编辑 `skills[]`、`model`、`source_names`、`timeout_seconds`、`parameters` 等 Node 配置字段。
- 引入隔离的图布局元数据，用于保存节点坐标和画布状态；执行语义仍以 `DagConfig`/`NodeConfig` 为准。
- 新增图编辑 API，用于读取节点原型、读取/保存 DAG 图状态、读取/保存节点配置，以及读取运行状态快照。
- 保存 DAG 和 Node 配置时继续复用 `RuntimeConfigEditor.save()`、`DagConfig`、`NodeConfig` 和 `load_graph()` 校验；非法图或非法节点配置不得写入。
- 多阶段交付：只读图展示、交互编辑保存、侧边栏配置、运行状态展示、最终替换表格入口。

## Capabilities

### New Capabilities
- `node-graph-dag-editor`: 覆盖 Node Graph DAG 编排界面、图状态 API、节点 palette、画布交互、Inspector 配置和运行状态叠加。

### Modified Capabilities
- `runtime-config-editing`: 将 DAG/Node 的主要 Web 编辑体验从 YAML/表格增强为 Node Graph，同时保留 YAML 兜底和原子校验保存语义。
- `pipeline-control`: 扩展运行状态展示语义，使 Web 控制台可以按 Node Graph 节点展示最近运行状态和错误信息。

## Impact

- **代码**: 预计新增 `src/stockimformation/web/static/node_graph_editor.js`、Node Graph 专用模板/样式/API helper，并调整 `routes.py` 和配置页面入口。
- **依赖**: 允许引入一个无构建链、可本地静态托管的节点图编辑库；优先评估 LiteGraph.js，因为 ComfyUI 风格与现有 Jinja 静态架构匹配。不得引入 React/Vite 全家桶，除非另行更新设计并说明迁移成本。
- **配置**: 现有 `config/dags/*.yaml` 继续保存执行语义；新增图布局元数据必须与执行语义隔离，第一选择为 DAG YAML 中的 `ui`/`metadata.ui` 字段或旁路 `config/dags/*.ui.yaml` 文件，最终由设计约束固定。
- **API/Web**: 新增图编辑 JSON API；保留现有 `/config`、`/config/dag` 和 raw YAML 保存路径作为兜底。
- **测试**: 需要覆盖图状态读取、DAG 保存校验、Node 配置保存校验、运行状态映射、页面加载和无构建静态资源可用性。
