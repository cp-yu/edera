# node-management-page Specification

## Purpose
此规约记录变更 node-type-instance-model 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Node management page routing
系统 SHALL 在顶级路由 `/nodes` 提供节点管理页面，侧边栏新增导航入口。

#### Scenario: Navigate to node management
- **WHEN** 用户点击侧边栏节点管理图标
- **THEN** 系统 SHALL 导航到 `/nodes` 页面

### Requirement: Tab-based organization
节点管理页面 SHALL 提供三个 tab：LLM 节点、Function 节点、Skills。

#### Scenario: Switch between tabs
- **WHEN** 用户点击不同 tab
- **THEN** 系统 SHALL 切换显示对应类型的列表和管理界面

### Requirement: LLM node type management
系统 SHALL 支持通过 UI 创建和编辑 LLM 节点类型。

#### Scenario: Create LLM node type
- **WHEN** 用户在 LLM 节点 tab 点击创建按钮并填写 name、role、system prompt、默认 skills、input_type、output_type、model
- **THEN** 系统 SHALL 调用 API 创建节点类型 YAML 和 prompt 文件

#### Scenario: Edit LLM node type
- **WHEN** 用户选中一个 LLM 节点类型并修改配置
- **THEN** 系统 SHALL 允许编辑 system prompt（在线编辑器）、默认 skills、I/O 类型、默认 model

#### Scenario: Delete LLM node type
- **WHEN** 用户删除一个无实例引用的 LLM 节点类型
- **THEN** 系统 SHALL 调用 API 删除对应文件

### Requirement: Function node type management

系统 SHALL 支持通过 UI 创建和编辑 Function 节点类型，并通过节点管理页顶层 Handler tab 编辑 Function 节点 handler 代码。

#### Scenario: Top-level handler tab

- **WHEN** 用户打开节点管理页面
- **THEN** 系统 SHALL 在 LLM 节点、Function 节点、Skills 同级展示"Handler" tab

#### Scenario: Function tab content

- **WHEN** 用户选择"Function 节点" tab
- **THEN** 系统 SHALL 展示 JSON 编辑器，包含节点元数据（name、type、role、handler、input_type、output_type、parameters），不包含 `handler_code` 字段

#### Scenario: Handler tab loads code from backend

- **WHEN** 用户选择顶层"Handler" tab
- **THEN** 系统 SHALL 调用 `GET /api/graph/handlers/{handler_name}` 加载 handler Python 代码并展示在 monospace 编辑器中

#### Scenario: Handler tab loading state

- **WHEN** handler 代码正在加载
- **THEN** 系统 SHALL 在编辑器区域展示 loading 指示

#### Scenario: Save handler code

- **WHEN** 用户在顶层 Handler tab 编辑代码后触发保存（blur 或保存按钮）
- **THEN** 系统 SHALL 调用 `PUT /api/graph/handlers/{handler_name}` 保存代码

#### Scenario: Create Function node type

- **WHEN** 用户在 Function 节点 tab 点击创建按钮
- **THEN** 系统 SHALL 创建节点类型并生成默认 handler 代码文件

#### Scenario: Delete Function node type

- **WHEN** 用户删除一个 Function 节点类型
- **THEN** 系统 SHALL 调用 API 删除对应 YAML 和 handler 文件

### Requirement: Skill management
系统 SHALL 支持通过 UI 创建、编辑和删除 Skills。

#### Scenario: Create skill
- **WHEN** 用户在 Skills tab 点击创建按钮并填写 name、description、handler 代码、parameters_schema
- **THEN** 系统 SHALL 调用 API 创建 skill YAML 和 handler 文件

#### Scenario: Edit skill
- **WHEN** 用户选中一个 skill 并修改
- **THEN** 系统 SHALL 允许编辑 description、handler 代码、parameters_schema

#### Scenario: Delete skill
- **WHEN** 用户删除一个 skill
- **THEN** 系统 SHALL 调用 API 删除对应 YAML 和 handler 文件

