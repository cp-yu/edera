## ADDED Requirements

### Requirement: 临时输入配置 UI
Web Console SHALL 在 DAG 运行按钮旁提供临时输入配置入口，打开弹窗支持配置 `sourceSharedInputs`、`nodeInputs`、`appendNodes`。

#### Scenario: 运行 DAG 时打开临时输入弹窗
- **WHEN** 用户点击"运行"按钮旁的配置图标
- **THEN** 系统 SHALL 打开临时输入配置弹窗

#### Scenario: 配置临时输入后运行
- **WHEN** 用户在弹窗中配置 `sourceSharedInputs` 和 `nodeInputs`，并勾选 `appendNodes`
- **THEN** 系统 SHALL 调用 run API 并传递这些参数

### Requirement: Retry 临时输入配置
Web Console 的 Canvas 右键菜单 SHALL 在 Retry 选项中增加临时输入配置入口。

#### Scenario: Retry 时打开临时输入弹窗
- **WHEN** 用户右键节点选择"Retry"并点击"配置输入"
- **THEN** 系统 SHALL 打开临时输入配置弹窗

#### Scenario: 配置临时输入后重试
- **WHEN** 用户在弹窗中配置临时输入
- **THEN** 系统 SHALL 调用 retry API 并传递这些参数
