## ADDED Requirements

### Requirement: Read runtime configuration
系统 SHALL 从现有 `config/` 和 `skills/` 目录读取可编辑配置，并通过 WebUI 展示。

#### Scenario: View portfolio config
- **WHEN** 用户打开配置编辑页面
- **THEN** 系统 SHALL 展示当前标的、持仓和信息源配置

#### Scenario: View node and dag config
- **WHEN** 用户打开 Node 或 DAG 配置页面
- **THEN** 系统 SHALL 展示对应 YAML 内容或等价结构化字段

### Requirement: Validate before save
系统 MUST 在写入配置文件前校验配置内容。

#### Scenario: Invalid portfolio rejected
- **WHEN** 用户提交不符合 schema 的 portfolio 配置
- **THEN** 系统 MUST 拒绝保存并返回校验错误

#### Scenario: Invalid dag rejected
- **WHEN** 用户提交引用不存在 Node 或形成环的 DAG 配置
- **THEN** 系统 MUST 拒绝保存并返回 DAG 校验错误

#### Scenario: Invalid node rejected
- **WHEN** 用户提交缺少 skill 或 I/O 类型不匹配的 Node 配置
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Atomic config save
系统 SHALL 以原子方式保存配置文件，避免半写入状态。

#### Scenario: Successful config save
- **WHEN** 用户提交合法配置
- **THEN** 系统 SHALL 写入目标配置文件，并保证写入过程中不会留下部分内容

### Requirement: Running cycle uses config snapshot
系统 SHALL 保证已经开始的管道周期使用启动时加载的配置快照。

#### Scenario: Edit config during active run
- **WHEN** 用户在管道运行中保存新配置
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新配置只影响后续运行

### Requirement: Skill document editing
系统 SHALL 支持查看和编辑 `skills/*` 下的 Skill 文档类文件，并限制编辑范围在项目 `skills/` 目录内。

#### Scenario: Save skill workflow
- **WHEN** 用户编辑合法 Skill 文档并保存
- **THEN** 系统 SHALL 写入对应 `skills/<name>/` 下的文件

#### Scenario: Reject path traversal
- **WHEN** 用户请求编辑 `skills/` 目录外的路径
- **THEN** 系统 MUST 拒绝该请求
