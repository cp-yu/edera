## MODIFIED Requirements

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
