## Why

当前项目存在严重的术语不一致问题，同一概念在代码、数据库、API 和文档中使用多个不同名称，导致理解成本高、维护困难。最突出的问题包括：Pipeline 与 DAG 混用（表名 `pipeline_runs` vs 类名 `DagConfig`）、cycle_id 与 run 概念分裂、Trigger 一词四义（Entity/Executor/RPC 动词/审计字段）。项目处于开发阶段无历史负担，现在是统一术语的最佳时机。

## What Changes

**BREAKING** 全面重命名核心术语和 API：

- **Pipeline → DAG**：所有 Pipeline 相关命名改为 DAG
  - 类：`PipelineController` → `DagController`，`PipelineRun` → `DagRun`
  - 表：`pipeline_runs` → `dag_runs`
  - 文件：`pipeline.py` → `dag_controller.py`，`pipeline_service.py` 拆分
  - 函数：`start_pipeline_run()` → `start_dag_run()`

- **cycle_id → run_id**：统一使用 run 作为执行实例标识
  - 数据库列：所有表的 `cycle_id` → `run_id`
  - Proto message：`DagRunRef.cycle_id` → `DagRunRef.run_id`
  - 代码变量：全局替换 `cycle_id` → `run_id`

- **Trigger 语义收敛**：消除 Trigger 一词多义
  - `DagService.Trigger` RPC → `DagService.Run`（动词改为"运行"）
  - `pipeline_runs.trigger` 列 → `dag_runs.source`（审计字段改名）
  - CLI：`edera dag trigger` → `edera dag run`

- **gRPC Service 重组**：按职责重新划分 service
  - 消灭 `PipelineService`，职责分散到 `DagService`、`EventService`、`SystemService`
  - `DagService`：管理单个 DAG 生命周期（Run/Stop/Retry/Status/Edit）
  - `EventService`（新）：事件注入（Emit）
  - `SystemService`：全局系统控制（PauseScheduler/ResumeScheduler/SchedulerStatus）

- **CLI 命令调整**：
  - `edera dag trigger` → `edera dag run`
  - `edera trigger emit` → `edera event emit`
  - 新增：`edera system pause-scheduler`、`edera system resume-scheduler`

- **数据库迁移**：Alembic migration 重命名表和列

## Capabilities

### New Capabilities

- `terminology-glossary`：项目术语表文档，定义所有核心概念的 canonical term、同义词和使用约定

### Modified Capabilities

- `cap.core.edera-server-grpc`：gRPC service 定义重组，DagService/EventService/SystemService 职责重新划分
- `cap.core.edera-cli`：CLI 子命令重命名（dag trigger → dag run，trigger emit → event emit）
- `cap.web.edera-web-bff`：BFF 路由适配新的 gRPC service 和 message 命名
- `cap.data.data-models`：数据模型重命名（PipelineRun → DagRun，cycle_id → run_id）
- `cap.operations.dag-event-driven-executor`：DagRunner 和 TriggerExecutor 代码中的术语统一
- `cap.operations.dag-run-control`：retry/resume 逻辑中的 cycle_id → run_id 替换

## Impact

**代码层**：
- Python 核心包：`edera_core/pipeline.py`、`edera_core/pipeline_service.py`、`edera_core/storage/entities.py`、`edera_core/dag/runner.py` 等 20+ 文件
- TypeScript 前端：`apps/web-console/src/api/types.ts`、`mutations.ts`、`queries.ts` 等 API 层文件
- Proto 定义：`proto/edera.proto` 全面重构 service 和 message

**数据库**：
- 表重命名：`pipeline_runs` → `dag_runs`
- 列重命名：`cycle_id` → `run_id`（影响 `dag_runs`、`node_runs`、`node_outputs`、`edge_inputs` 等 5 张表）
- 列重命名：`dag_runs.trigger` → `dag_runs.source`
- 外键约束重建

**API 兼容性**：
- **BREAKING**：所有 gRPC RPC 路径变更（`/edera.v1.DagService/Trigger` → `/edera.v1.DagService/Run`）
- **BREAKING**：Proto message 字段变更（`cycle_id` → `run_id`）
- **BREAKING**：`PipelineService` 消失，客户端需迁移到新 service

**CLI**：
- **BREAKING**：子命令重命名（`edera dag trigger` → `edera dag run`）

**文档**：
- 新增 `GLOSSARY.md` 术语表
- 更新所有 OpenSpec artifacts 中的术语引用
