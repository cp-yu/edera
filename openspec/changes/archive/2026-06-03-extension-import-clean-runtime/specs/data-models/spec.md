## MODIFIED Requirements

### Requirement: DagRun 数据模型
系统 SHALL 定义 DagRun 模型存储 DAG 执行记录，MUST 包含：run_id（唯一标识）、dag_name、source（发起来源）、status、started_at、ended_at、error、retry_of。`PipelineRun` 类名已废弃，改为 `DagRun`。表名从 `pipeline_runs` 改为 `dag_runs`。

#### Scenario: 创建 DagRun 记录
- **WHEN** DAG 开始执行
- **THEN** 系统创建 DagRun 记录，`run_id` 为 UUID，`source` 标注发起方式

#### Scenario: source 字段合法值
- **WHEN** 系统创建 DagRun 记录
- **THEN** `source` 字段 SHALL 为以下值之一：`manual`、`retry`、`trigger:<trigger_name>`

#### Scenario: startup source rejected
- **WHEN** 系统尝试创建 `source = "startup"` 的 DagRun
- **THEN** 系统 MUST 拒绝该记录

#### Scenario: Trigger Entity fire 时记录 source
- **WHEN** Trigger Entity `morning-cron` fire 启动 DAG
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `trigger:morning-cron`

#### Scenario: 手动运行记录 source
- **WHEN** 用户通过 CLI 或 UI 手动运行 DAG
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `manual`

#### Scenario: 重试记录 source
- **WHEN** 用户重试失败的 run
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `retry`
