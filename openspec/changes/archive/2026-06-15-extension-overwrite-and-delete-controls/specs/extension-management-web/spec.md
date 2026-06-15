## MODIFIED Requirements

### Requirement: 安装操作

用户 SHALL 可以在页面中安装可用扩展。安装请求 SHALL 支持覆盖参数：用户 MUST 能够选择对已安装扩展执行覆盖安装。覆盖安装请求 SHALL 将 overwrite 语义透传至 `ExtensionService.Install`，并在结果中展示数据保留提醒。Web 控制台 MUST NOT 提供删除扩展源目录或批量导入实体数据的入口（这两类操作仅通过 CLI 与 gRPC 暴露）。

#### Scenario: 从页面安装扩展

- **WHEN** 用户点击可用扩展的"安装"按钮
- **THEN** 页面 SHALL 调用 `ExtensionService.Install`（overwrite=false）
- **AND** 安装成功后刷新扩展列表
- **AND** 安装失败时展示错误信息

#### Scenario: 从页面覆盖安装已安装扩展

- **WHEN** 用户对已安装扩展发起覆盖安装请求（overwrite=true）
- **THEN** 页面 SHALL 调用 `ExtensionService.Install`（overwrite=true）
- **AND** 安装成功后刷新扩展列表
- **AND** 页面 SHALL 展示返回结果中的数据保留提醒
