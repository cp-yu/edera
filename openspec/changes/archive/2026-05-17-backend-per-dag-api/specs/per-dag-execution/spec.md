## Purpose

定义 per-DAG 并发执行模型，覆盖 per-DAG 锁机制、并发运行管理、per-DAG 调度注册和 per-DAG 运行/停止/状态 API。

## ADDED Requirements

### Requirement: Per-DAG concurrent execution
系统 SHALL 支持不同 DAG 并发执行，同一 DAG 同一时间 MUST 只允许一个活跃运行。

#### Scenario: Start run for idle DAG
- **WHEN** 用户对一个当前无活跃运行的 DAG 触发运行
- **THEN** 系统 SHALL 创建新 cycle 并启动该 DAG 的执行任务

#### Scenario: Reject concurrent run for same DAG
- **WHEN** 用户对一个已有活跃运行的 DAG 再次触发运行
- **THEN** 系统 MUST 拒绝并返回当前活跃运行的 cycle_id

#### Scenario: Allow concurrent runs for different DAGs
- **WHEN** DAG-A 正在运行且用户触发 DAG-B 运行
- **THEN** 系统 SHALL 允许 DAG-B 启动，两个 DAG 并行执行互不阻塞

### Requirement: Per-DAG run API
系统 SHALL 提供按 DAG 名称触发运行的 API 端点。

#### Scenario: Trigger named DAG run
- **WHEN** 客户端发送 `POST /api/pipeline/dag/{dag_name}/run`
- **THEN** 系统 SHALL 加载指定 DAG 配置并启动执行，返回新 cycle_id

#### Scenario: Trigger non-existent DAG
- **WHEN** 客户端发送 `POST /api/pipeline/dag/{dag_name}/run` 且该 DAG 不存在于配置中
- **THEN** 系统 MUST 返回 404 错误

### Requirement: Per-DAG stop API
系统 SHALL 提供按 DAG 名称停止运行的 API 端点。

#### Scenario: Stop running DAG
- **WHEN** 客户端发送 `POST /api/pipeline/dag/{dag_name}/stop` 且该 DAG 有活跃运行
- **THEN** 系统 SHALL 取消该 DAG 的执行任务并返回被停止的 cycle_id

#### Scenario: Stop idle DAG
- **WHEN** 客户端发送 `POST /api/pipeline/dag/{dag_name}/stop` 且该 DAG 无活跃运行
- **THEN** 系统 SHALL 返回无活跃运行状态

### Requirement: Per-DAG status API
系统 SHALL 提供按 DAG 名称查询运行状态的 API 端点。

#### Scenario: Query DAG status
- **WHEN** 客户端发送 `GET /api/pipeline/dag/{dag_name}/status`
- **THEN** 系统 SHALL 返回该 DAG 的当前运行状态（cycle_id、status）和最近运行记录列表

#### Scenario: Query status with node details
- **WHEN** 客户端查询正在运行的 DAG 状态
- **THEN** 系统 SHALL 包含各节点的实时执行状态（pending/running/succeeded/failed）

### Requirement: Per-DAG scheduler registration
系统 SHALL 在启动时为每个已配置的 DAG 注册独立的定时调度 job。

#### Scenario: Register scheduler jobs on startup
- **WHEN** 系统启动且 `config/dags/` 目录下存在多个 DAG 配置文件
- **THEN** 系统 SHALL 为每个 DAG 注册独立的 APScheduler interval job

#### Scenario: Scheduler respects per-DAG mutex
- **WHEN** 调度器触发某 DAG 的定时运行但该 DAG 已有活跃运行
- **THEN** 系统 SHALL 静默跳过本次触发，不创建新运行

### Requirement: PipelineRun dag_name field
系统 SHALL 在 `PipelineRun` 记录中持久化 DAG 名称。

#### Scenario: Record dag_name in pipeline run
- **WHEN** 系统创建新的 PipelineRun 记录
- **THEN** 系统 MUST 将触发运行的 DAG 名称写入 `dag_name` 字段

#### Scenario: Default dag_name for legacy records
- **WHEN** 系统读取不含 `dag_name` 字段的历史记录
- **THEN** 系统 SHALL 将其视为 `"default"` DAG 的运行记录
