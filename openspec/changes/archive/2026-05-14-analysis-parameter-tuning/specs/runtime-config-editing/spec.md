## ADDED Requirements

### Requirement: Analysis parameter tuning entry
系统 SHALL 在 Web 配置界面提供分析参数调优入口，帮助用户定位会影响分析链结果的运行时配置。

#### Scenario: View analysis tuning entry
- **WHEN** 用户打开 Web 配置界面
- **THEN** 系统 SHALL 提供分析参数调优入口，并展示可调参数对应的配置来源

#### Scenario: Preserve generic config editing
- **WHEN** 用户使用通用配置编辑入口
- **THEN** 系统 SHALL 继续支持编辑 `system`、`portfolio`、`node`、`dag` 和 `skill` 配置

### Requirement: Bounded analysis parameters
系统 MUST 将第一版分析参数调优限制在 schema 明确允许的配置字段内，包括 `NodeConfig.timeout_seconds`、`NodeConfig.model`、采集节点 `source_names`、`SystemConfig.llm_timeout_seconds`，以及节点 YAML 中的 `parameters` mapping。

#### Scenario: Show supported node parameters
- **WHEN** 用户查看分析参数调优入口
- **THEN** 系统 SHALL 展示 reader/advisor/briefing 相关节点中可编辑的 `model`、`timeout_seconds` 和 `parameters` 字段

#### Scenario: Show analysis input source parameters
- **WHEN** 用户查看分析参数调优入口
- **THEN** 系统 SHALL 展示采集节点的 `source_names`，用于调整后续分析输入范围

#### Scenario: Reject unsupported analysis parameter
- **WHEN** 用户提交 schema 未允许的分析参数字段
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Node private tuning parameters
系统 SHALL 支持在 Node YAML 中配置 `parameters` mapping，用于节点私有、非凭据、可序列化的分析调优参数。

#### Scenario: Save node parameters
- **WHEN** 用户为 reader、advisor 或 briefing 节点提交合法 `parameters` mapping
- **THEN** 系统 SHALL 保存对应 Node YAML，并让新参数仅影响后续运行

#### Scenario: Reject invalid node parameters
- **WHEN** 用户提交不可序列化或不符合 schema 的 `parameters` 内容
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Analysis tuning save semantics
系统 SHALL 复用运行时配置编辑的保存前校验、原子写入和运行中配置快照语义保存分析参数。

#### Scenario: Save valid analysis tuning
- **WHEN** 用户在分析参数调优入口提交合法参数
- **THEN** 系统 SHALL 原子写入对应配置文件，并返回保存成功状态

#### Scenario: Active run keeps previous parameters
- **WHEN** 用户在管道运行中保存新的分析参数
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新参数只影响后续运行

### Requirement: Analysis tuning rollback boundary
系统 SHALL 在第一版明确分析参数调优不提供内置版本历史或一键回滚。

#### Scenario: Save without internal version history
- **WHEN** 用户保存分析参数
- **THEN** 系统 SHALL 不创建数据库参数版本记录，并 SHALL 保持配置文件为唯一运行时参数来源
