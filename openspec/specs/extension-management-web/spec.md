# extension-management-web Specification

## Purpose
此规约记录变更 extension-active-management 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 扩展管理页面路由

WebConsole SHALL 在导航中新增"扩展"入口，路由为 `/extensions`。

#### Scenario: 访问扩展管理页面

- **WHEN** 用户在 WebConsole 导航中点击"扩展"或访问 `/extensions`
- **THEN** 系统 SHALL 展示扩展管理页面，包含已安装和可用扩展列表

### Requirement: 已安装扩展列表

页面 SHALL 展示所有已安装扩展，包含 name、version、启用状态。

#### Scenario: 展示已安装扩展

- **WHEN** 扩展管理页面加载
- **THEN** 页面 SHALL 调用 `ExtensionService.ListInstalled`
- **AND** 展示每个扩展的 name、version、enabled 状态
- **AND** 已停用扩展 SHALL 有明显的视觉区分

### Requirement: 可用扩展列表

页面 SHALL 展示 `extensions/` 目录中可用但未安装的扩展。

#### Scenario: 展示可用未安装扩展

- **WHEN** 扩展管理页面加载
- **THEN** 页面 SHALL 调用 `ExtensionService.ListAvailable`
- **AND** 过滤掉已安装的扩展后展示剩余可用扩展
- **AND** 每个可用扩展旁 SHALL 有"安装"操作入口

### Requirement: 安装操作

用户 SHALL 可以在页面中安装可用扩展。

#### Scenario: 从页面安装扩展

- **WHEN** 用户点击可用扩展的"安装"按钮
- **THEN** 页面 SHALL 调用 `ExtensionService.Install`
- **AND** 安装成功后刷新扩展列表
- **AND** 安装失败时展示错误信息

### Requirement: 卸载操作

用户 SHALL 可以在页面中卸载已安装扩展，MUST 选择卸载策略。

#### Scenario: 从页面卸载扩展

- **WHEN** 用户点击已安装扩展的"卸载"按钮
- **THEN** 页面 SHALL 弹出策略选择对话框，提供 purge、keep-modified、deactivate 三个选项
- **AND** 用户选择后调用 `ExtensionService.Uninstall`

#### Scenario: 卸载存在依赖

- **WHEN** 卸载请求返回依赖错误
- **THEN** 页面 SHALL 展示依赖扩展列表，不执行卸载

### Requirement: 扩展详情展示

用户 SHALL 可以查看扩展的详细信息。

#### Scenario: 查看扩展详情

- **WHEN** 用户点击扩展名称
- **THEN** 页面 SHALL 展示 manifest 内容：name、version、description、depends、handlers 列表、entity_types 列表、imports.entities 列表

