---
capabilities:
  - cap.web.node-graph-dag-editor
---
# node-graph-dag-editor Specification

## Purpose
定义 Node Graph editor entry、Graph schema API、Interactive graph editing、Graph DAG save等能力。
## Requirements
### Requirement: Node Graph editor entry
系统 SHALL 在 Web 控制台提供 Node Graph DAG 编辑入口，并将其作为 DAG 可视化编辑的主入口。

#### Scenario: Open Node Graph editor
- **WHEN** 用户打开 DAG 编辑入口
- **THEN** 系统 SHALL 展示包含节点 palette、画布和 Inspector 区域的 Node Graph 页面

#### Scenario: Preserve fallback editors
- **WHEN** 用户需要直接排查配置
- **THEN** 系统 SHALL 保留 raw YAML 或结构化表格编辑入口作为兜底

### Requirement: Graph schema API
系统 SHALL 提供图编辑所需的节点原型和 DAG 图状态 JSON API，避免前端直接解析 YAML。

#### Scenario: Load node prototypes
- **WHEN** Node Graph 编辑器加载
- **THEN** 系统 SHALL 返回可用 Node 原型，包括 `name`、`type`、`input_type`、`output_type`、`skills`、`model`、`source_names`、`timeout_seconds` 和 `parameters`

#### Scenario: Load DAG graph state
- **WHEN** Node Graph 编辑器打开指定 DAG
- **THEN** 系统 SHALL 返回该 DAG 的节点实例、边、fan flags 和 UI 布局元数据

### Requirement: Interactive graph editing
系统 SHALL 支持用户在画布上通过节点和端口交互编辑 DAG 数据流。画布 SHALL 实现完整的拖放（drop）、连线（connect）和删除（delete）交互。

#### Scenario: Add node from palette via drop
- **WHEN** 用户从 palette 拖拽一个 Node 到画布并释放
- **THEN** 系统 SHALL 调用 `onDrop` 处理器，在释放坐标处创建节点实例并加入 DAG 草稿

#### Scenario: Connect node ports
- **WHEN** 用户从上游节点的 source Handle 拖拽连线到下游节点的 target Handle
- **THEN** 系统 SHALL 通过 `onConnect` 回调在 DAG 草稿中创建对应边，edge 记录 `sourceHandle` 和 `targetHandle` 标识

#### Scenario: Delete graph edge
- **WHEN** 用户选中画布上的连线并按 Delete 键
- **THEN** 系统 SHALL 通过 `onEdgesDelete` 从 DAG 草稿中移除对应边

#### Scenario: Drag node on canvas
- **WHEN** 用户在画布上拖动节点
- **THEN** 节点 SHALL 跟随鼠标移动，位置变更仅更新本地状态，不触发从服务端重建

#### Scenario: Canvas resize follows container
- **WHEN** 浏览器窗口尺寸变化或容器布局改变
- **THEN** 画布分辨率 SHALL 自动匹配容器实际像素尺寸，交互坐标保持准确

### Requirement: Graph DAG save
系统 MUST 将 Node Graph 草稿保存回 DB-backed DAG Entity，包含 Handle 元数据。

#### Scenario: Save valid graph DAG with handle metadata
- **WHEN** 用户保存合法 Node Graph DAG
- **THEN** 系统 SHALL 写回对应 DAG 配置，`ui.nodes` 保存节点位置，`ui.edges` 保存 edge 的 sourceHandle/targetHandle 信息

#### Scenario: Reject invalid graph DAG
- **WHEN** 用户保存包含环、未知节点或 I/O 类型不匹配的 Node Graph DAG
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG 文件内容不变

#### Scenario: Reject sub-DAG nesting cycle
- **WHEN** 用户保存的 Node Graph DAG 包含 `type: "dag"` 且 `dag_ref` 指向当前 DAG 或形成间接 sub-DAG 环
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG Entity 内容不变

### Requirement: Node Inspector configuration
系统 SHALL 在 Node Graph Inspector 中根据 `inspector_schema` 展示 schema 驱动的可配置字段。

#### Scenario: Inspect node configuration by schema
- **WHEN** 用户选中画布中的节点
- **THEN** 系统 SHALL 根据 `inspector_schema` 在 Inspector 展示对应的编辑控件集合，不再使用硬编码的节点类型条件逻辑

#### Scenario: Save node configuration
- **WHEN** 用户在 Inspector 中保存合法节点配置
- **THEN** 系统 SHALL 将 schema 字段拆分回实例 `config`（顶层字段如 `model`/`skills` 保留在 config 顶层，`param.*` 前缀字段写入 `config.parameters`），并通过 `PUT /api/graph/dag/{name}` 持久化

#### Scenario: Reject invalid node configuration
- **WHEN** 用户在 Inspector 中保存非法节点配置
- **THEN** 系统 MUST 拒绝保存、返回可读错误并保持原 DAG 配置不变

### Requirement: Graph runtime status overlay
系统 SHALL 在 Node Graph 中展示最近或当前运行的节点状态。

#### Scenario: Show node run status
- **WHEN** Node Graph 编辑器加载运行状态
- **THEN** 系统 SHALL 在对应节点上展示 `pending`、`running`、`succeeded`、`failed` 或 `unknown` 状态

#### Scenario: Show node failure details
- **WHEN** 某节点最近运行失败
- **THEN** 系统 SHALL 在节点或 Inspector 中展示该节点的错误信息

### Requirement: Create node and add to DAG
系统 SHALL 提供 `POST /api/graph/dag/{name}/nodes` 端点，创建新 Node type Entity 并将其实例加入指定 DAG 的节点列表。

#### Scenario: Create node successfully
- **WHEN** 前端提交合法的节点定义（含 name、type、input_type、output_type）
- **THEN** 系统 SHALL 创建 Node type Entity、将节点实例追加到 DAG Entity 的 nodes 列表、并返回创建后的节点数据

#### Scenario: Node name conflicts with existing node
- **WHEN** 提交的节点 name 与已有节点文件同名
- **THEN** 系统 MUST 返回 409 错误，包含 `conflict` 错误类型

#### Scenario: Target DAG not found
- **WHEN** 指定的 DAG name 不存在于 DB-backed DAG Entity 表
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: DAG persistence format
系统 SHALL 使用实例对象列表格式持久化 DAG 配置，每个节点为包含 UUID id、类型引用和实例配置的对象。

#### Scenario: Save DAG with instance format
- **WHEN** 系统保存 DAG 配置到 YAML
- **THEN** 系统 SHALL 将 `nodes` 序列化为对象列表，每个对象包含 `id`（UUID）、`type`（节点类型名）、`alias`（可选）、`config`（实例级覆盖参数）

#### Scenario: Edge references use instance UUID
- **WHEN** 系统保存 DAG 边配置
- **THEN** 系统 SHALL 使用实例 UUID 作为 `from` 和 `to` 字段的值

#### Scenario: Load DAG with instance format
- **WHEN** 系统加载 DAG YAML 文件
- **THEN** 系统 SHALL 解析每个节点对象，通过 `type` 字段关联节点类型定义，通过 `config` 字段覆盖运行时参数

### Requirement: Handle rendering driven by role
系统 SHALL 根据节点类型的 `role` 决定 Handle 的渲染：source 节点不渲染输入 Handle，sink 节点不渲染输出 Handle。

#### Scenario: Source node has no input handle
- **WHEN** 画布渲染一个 `role: source` 的节点实例
- **THEN** 系统 SHALL 仅渲染右侧输出 Handle，不渲染左侧输入 Handle

#### Scenario: Sink node has no output handle
- **WHEN** 画布渲染一个 `role: sink` 的节点实例
- **THEN** 系统 SHALL 仅渲染左侧输入 Handle，不渲染右侧输出 Handle

#### Scenario: Processor node has both handles
- **WHEN** 画布渲染一个 `role: processor` 的节点实例
- **THEN** 系统 SHALL 同时渲染左侧输入 Handle 和右侧输出 Handle

### Requirement: Instance-aware Inspector
系统 SHALL 在选中节点实例时展示 schema 驱动的配置表单，根据后端返回的 `inspector_schema` 动态渲染编辑字段。

#### Scenario: Schema-driven form rendering
- **WHEN** 用户选中画布中的节点实例
- **THEN** 系统 SHALL 读取该实例的 `inspector_schema`，为每个 schema property 渲染对应 UI 控件：`string` 渲染文本输入、`string + enum` 渲染下拉选择、`integer/number` 渲染数字输入、`boolean` 渲染开关

#### Scenario: LLM instance Inspector
- **WHEN** 用户选中一个 LLM 节点实例
- **THEN** 系统 SHALL 展示可编辑字段：`alias`（独立文本输入）、`model`（下拉选择）、`skills`（多选标签）、`timeout_seconds`（数字输入），以及 `parameters_schema` 定义的自定义字段

#### Scenario: Function instance Inspector
- **WHEN** 用户选中一个 Function 节点实例
- **THEN** 系统 SHALL 展示可编辑字段：`alias`（独立文本输入）、`source_names`（多选标签，仅 source role）、`timeout_seconds`（数字输入），以及 `parameters_schema` 定义的自定义字段

#### Scenario: Read-only type info display
- **WHEN** 用户选中任意节点实例
- **THEN** 系统 SHALL 以只读方式展示类型信息：`type_name`、`role`、`input_type`、`output_type`

#### Scenario: Value display priority
- **WHEN** schema 驱动表单渲染字段值
- **THEN** 系统 SHALL 优先显示实例 `config` 中的值；若无，显示类型默认值；placeholder SHALL 显示类型默认值以提示回退目标

#### Scenario: Clear field reverts to type default
- **WHEN** 用户清空某个 schema 字段的值并保存
- **THEN** 系统 SHALL 从实例 `config` 中删除该字段，运行时回退到类型默认值

#### Scenario: Diff-only save
- **WHEN** 用户保存实例配置
- **THEN** 系统 SHALL 仅将与类型默认值不同的字段写入实例 `config`，不存储与默认值相同的冗余数据

#### Scenario: Unsupported schema type fallback
- **WHEN** `inspector_schema` 中某字段的类型不在支持列表（`string`、`integer`、`number`、`boolean`）中
- **THEN** 系统 SHALL 将该字段渲染为 raw JSON 文本输入

#### Scenario: Deselect node clears Inspector
- **WHEN** 用户点击画布空白区域取消选中
- **THEN** Inspector SHALL 清空节点配置显示
