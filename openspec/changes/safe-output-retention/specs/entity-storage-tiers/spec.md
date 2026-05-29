## MODIFIED Requirements

### Requirement: 输出型 Entity retention 策略

系统 SHALL 对数据库层的输出型 Entity 执行 retention 清理。清理策略 MUST 可通过 `system.toml` 配置。默认 `retention_hours` SHALL 为 720。系统 MUST 只在完整 DAG run 成功完成后触发输出型 Entity retention 清理；失败 run、取消 run、单节点运行和 partial retry MUST NOT 触发 retention 清理。

#### Scenario: 按保留数量清理

- **WHEN** `system.toml` 配置 `retention_count: 20`，且当前已有 25 次 run 的输出 Entity
- **THEN** 系统清理最早 5 次 run 产生的所有输出型 Entity

#### Scenario: 按保留时间清理

- **WHEN** `system.toml` 配置 `retention_hours: 720`，且存在超过 720 小时的输出 Entity
- **THEN** 系统清理这些过期的输出型 Entity

#### Scenario: 成功完整 DAG run 触发 retention

- **WHEN** 完整 DAG run 成功完成
- **THEN** 系统 SHALL 执行输出型 Entity retention 清理

#### Scenario: 失败或取消 DAG run 不触发 retention

- **WHEN** DAG run 以 `failed` 或 `cancelled` 状态结束
- **THEN** 系统 MUST NOT 执行输出型 Entity retention 清理

#### Scenario: 非完整 DAG run 不触发 retention

- **WHEN** 单节点运行或 partial retry 完成
- **THEN** 系统 MUST NOT 执行输出型 Entity retention 清理
