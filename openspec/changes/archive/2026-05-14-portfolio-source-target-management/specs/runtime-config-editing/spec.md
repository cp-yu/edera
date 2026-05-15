## ADDED Requirements

### Requirement: Structured portfolio management entry
系统 SHALL 在 Web 配置界面提供结构化标的与信息源管理入口，展示 `portfolio.yaml` 中的 targets、holdings、sources 和绑定关系。

#### Scenario: View portfolio targets and sources
- **WHEN** 用户打开 Web 配置界面
- **THEN** 系统 SHALL 展示当前标的、持仓数量、成本价、绑定的信息源和所有可用信息源

#### Scenario: Preserve raw portfolio editing
- **WHEN** 用户需要直接编辑 `portfolio.yaml`
- **THEN** 系统 SHALL 继续提供通用配置编辑入口

### Requirement: Structured portfolio save
系统 SHALL 支持通过结构化 Web/API 请求保存 portfolio targets 和 sources，并写回现有 `config/portfolio.yaml`。

#### Scenario: Save valid portfolio structure
- **WHEN** 用户提交符合 `PortfolioConfig` schema 的 targets 和 sources
- **THEN** 系统 SHALL 原子写入 `portfolio.yaml`，并返回保存成功状态

#### Scenario: Reject invalid portfolio structure
- **WHEN** 用户提交非法 URL、非法 source type、负数持仓或缺失必填字段
- **THEN** 系统 MUST 拒绝保存并返回校验错误

#### Scenario: Reject target source reference to missing source
- **WHEN** 用户提交的 target 引用不存在的信息源名称
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Portfolio save semantics
系统 SHALL 复用运行时配置编辑的保存前校验、原子写入和运行中配置快照语义保存 portfolio 管理变更。

#### Scenario: Active run keeps previous portfolio
- **WHEN** 用户在管道运行中保存新的标的或信息源配置
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新配置只影响后续运行
