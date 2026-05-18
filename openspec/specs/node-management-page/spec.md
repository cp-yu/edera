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
系统 SHALL 支持通过 UI 创建和编辑 Function 节点类型，包含代码编辑。

#### Scenario: Create Function node type
- **WHEN** 用户在 Function 节点 tab 点击创建按钮并填写 name、role、handler 代码、input_type、output_type
- **THEN** 系统 SHALL 调用 API 创建节点类型 YAML 和 handler Python 文件

#### Scenario: Edit Function handler code
- **WHEN** 用户选中一个 Function 节点类型
- **THEN** 系统 SHALL 展示内嵌代码编辑器，显示 handler Python 代码，支持编辑和保存

#### Scenario: View Function node details
- **WHEN** 用户查看 Function 节点类型详情
- **THEN** 系统 SHALL 展示 handler 代码、I/O 类型、role、parameters schema

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

