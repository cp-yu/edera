## MODIFIED Requirements

### Requirement: Briefing 数据模型
系统 SHALL 定义 Briefing 模型存储简报，MUST 包含：run_id、content（简报正文）、metadata（配置源列表/成功源列表/失败源列表/数据时间窗口）、created_at。`cycle_id` 字段已废弃，改为 `run_id`。

#### Scenario: 创建带元数据的 Briefing
- **WHEN** 简报生成节点完成简报
- **THEN** Briefing 记录的 metadata 包含本周期所有信息源的采集状态
- **AND** Briefing 记录的 `run_id` 字段关联到对应的 DAG run

#### Scenario: 通过 run_id 查询 Briefing
- **WHEN** 用户查询特定 run 的简报
- **THEN** 系统 SHALL 通过 `run_id` 字段过滤（如 `WHERE run_id = 'abc123'`）

## ADDED Requirements

### Requirement: DagRun 数据模型
系统 SHALL 定义 DagRun 模型存储 DAG 执行记录，MUST 包含：run_id（唯一标识）、dag_name、source（发起来源）、status、started_at、ended_at、error、retry_of。`PipelineRun` 类名已废弃，改为 `DagRun`。表名从 `pipeline_runs` 改为 `dag_runs`。

#### Scenario: 创建 DagRun 记录
- **WHEN** DAG 开始执行
- **THEN** 系统创建 DagRun 记录，`run_id` 为 UUID，`source` 标注发起方式

#### Scenario: source 字段合法值
- **WHEN** 系统创建 DagRun 记录
- **THEN** `source` 字段 SHALL 为以下值之一：`manual`、`startup`、`retry`、`trigger:<trigger_name>`

#### Scenario: Trigger Entity fire 时记录 source
- **WHEN** Trigger Entity `morning-cron` fire 启动 DAG
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `trigger:morning-cron`

#### Scenario: 手动运行记录 source
- **WHEN** 用户通过 CLI 或 UI 手动运行 DAG
- **THEN** DagRun 记录的 `source` 字段 SHALL 为 `manual`

#### Scenario: 重试记录 source
- **WHEN** 用户重试失败的 run
- **THEN** 新 DagRun 记录的 `source` 字段 SHALL 为 `retry`，`retry_of` 字段关联原 run_id

### Requirement: NodeRun 数据模型使用 run_id
系统 SHALL 定义 NodeRun 模型存储节点执行记录，MUST 包含：run_id（外键关联 dag_runs.run_id）、node_name、status、started_at、ended_at、error、failure_kind。`cycle_id` 字段已废弃，改为 `run_id`。

#### Scenario: 创建 NodeRun 记录
- **WHEN** 节点开始执行
- **THEN** 系统创建 NodeRun 记录，`run_id` 关联到父 DagRun

#### Scenario: Sub-DAG 记录 parent_run_id
- **WHEN** 子 DAG 作为节点执行
- **THEN** 子 DAG 的 NodeRun 记录的 `metadata.parent_run_id` 字段 SHALL 关联到父 run_id
- **AND** 子 DAG 的 DagRun 有独立的 `run_id`

### Requirement: NodeOutput 数据模型使用 run_id
系统 SHALL 定义 NodeOutput 模型存储节点输出，MUST 包含：run_id（外键关联 dag_runs.run_id）、node_id、payload、ok、created_at。`cycle_id` 字段已废弃，改为 `run_id`。

#### Scenario: 创建 NodeOutput 记录
- **WHEN** 节点执行完成
- **THEN** 系统创建 NodeOutput 记录，`run_id` 关联到对应的 DAG run

### Requirement: EdgeInput 数据模型使用 run_id
系统 SHALL 定义 EdgeInput 模型存储边输入事实，MUST 包含：run_id（外键关联 dag_runs.run_id）、from_node、to_node、payload、created_at。`cycle_id` 字段已废弃，改为 `run_id`。

#### Scenario: 记录 edge input fact
- **WHEN** DAG dispatcher 在节点调度决策点生成边输入事实
- **THEN** 系统创建 EdgeInput 记录，`run_id` 关联到对应的 DAG run

### Requirement: 数据库迁移
系统 SHALL 提供 Alembic migration 脚本，重命名表和列。

#### Scenario: 表重命名
- **WHEN** 执行 migration
- **THEN** 系统 SHALL 将 `pipeline_runs` 表重命名为 `dag_runs`

#### Scenario: 列重命名
- **WHEN** 执行 migration
- **THEN** 系统 SHALL 将所有表的 `cycle_id` 列重命名为 `run_id`
- **AND** 系统 SHALL 将 `dag_runs.trigger` 列重命名为 `dag_runs.source`

#### Scenario: 外键约束重建
- **WHEN** 执行 migration
- **THEN** 系统 SHALL 删除旧的 `cycle_id` 外键约束
- **AND** 系统 SHALL 创建新的 `run_id` 外键约束

