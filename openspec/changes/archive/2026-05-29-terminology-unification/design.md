## Context

当前 Edera 项目在术语使用上存在严重不一致：
- **Pipeline vs DAG**：数据库表名 `pipeline_runs`、类名 `PipelineController`、文件名 `pipeline.py`，但配置文件、UI、文档都使用 DAG
- **cycle_id vs run**：数据库主键和 proto 字段用 `cycle_id`，但类名、函数名、用户界面都用 "run"
- **Trigger 多义**：同时指代 Trigger Entity（配置）、TriggerExecutor（运行时）、`DagService.Trigger` RPC（手动运行动词）、`pipeline_runs.trigger` 列（审计字段）
- **Service 职责混乱**：`PipelineService` 既管全局 scheduler 控制（Pause/Resume），又管单 DAG 操作（DagStop/DagRetry），还管事件注入（Emit）

项目当前处于开发阶段，无外部客户端依赖，允许 breaking change。trigger-system-redesign 已完成，所有 DAG 启动统一走 TriggerExecutor，为术语统一提供了良好基础。

## Goals / Non-Goals

**Goals:**
- 消灭 Pipeline 术语，全面使用 DAG
- 统一 cycle_id → run_id，消除概念分裂
- 收敛 Trigger 语义，让每个术语只有一个明确含义
- 按职责重组 gRPC service，清晰划分 DAG 操作、事件管理、系统控制
- 建立项目术语表（GLOSSARY.md），作为未来开发的权威参考
- 一次性完成所有重命名，避免"半统一"中间态

**Non-Goals:**
- 不改变功能行为，纯重命名和重组
- 不引入新的调度机制或触发逻辑
- 不优化现有代码结构（如 DagController 内部实现）
- 不处理 UI 文案翻译（保持现有中文标签）
- 不迁移历史数据（开发阶段可清空数据库）

## Decisions

### D1: Pipeline 全面改为 DAG

**选择**：所有 Pipeline 相关命名改为 DAG，包括类名、表名、文件名、函数名

**替代方案**：保留 Pipeline 作为"全局 controller"语义，DAG 作为"单个图"语义

**理由**：
- project.opsx.yaml 中项目定位明确为"以 DAG 为执行模型"
- 用户界面、配置文件、文档已全面使用 DAG
- Pipeline 和 DAG 语义重叠，保留两者会持续混淆
- 当前 `PipelineController` 实际管理的就是 DAG 的运行，改名为 `DagController` 更准确

**影响**：
- 文件重命名：`pipeline.py` → `dag_controller.py`
- 类重命名：`PipelineController` → `DagController`，`PipelineRun` → `DagRun`
- 表重命名：`pipeline_runs` → `dag_runs`
- 函数重命名：`create_pipeline_run()` → `create_dag_run()`，约 30+ 函数

### D2: cycle_id 全面改为 run_id

**选择**：数据库列、proto 字段、代码变量全部使用 `run_id`

**替代方案 A**：保留 `cycle_id` 作为内部标识符，`run` 作为用户概念  
**替代方案 B**：全部改为 `cycle`

**理由**：
- "run" 是用户自然理解的概念（"一次运行"），cycle 有"循环"歧义
- 当前代码中 `run` 已广泛使用（`start_run`、`run_now`、`PipelineRun`、`NodeRun`）
- 开发阶段无历史负担，DB migration 成本低
- 统一后 `run_id` 作为 Run 的唯一标识符，语义清晰（类似 `user_id` 是 User 的主键）

**影响**：
- 数据库：5 张表的 `cycle_id` 列改名（`dag_runs`、`node_runs`、`node_outputs`、`edge_inputs`、`emit_records`）
- Proto：`DagRunRef.cycle_id` → `DagRunRef.run_id`
- 代码：全局替换 `cycle_id` → `run_id`（约 200+ 处）
- 外键约束需要先删除再重建

### D3: DagService.Trigger RPC 改名为 Run

**选择**：`DagService.Trigger(DagTriggerRequest)` → `DagService.Run(DagRunRequest)`

**替代方案 A**：移到新的 `TriggerService.EmitManual`  
**替代方案 B**：复用 `EventService.Emit`，event="manual:dag/<name>"

**理由**：
- 用户意图是"运行一次 DAG"，不是"触发一个 trigger"
- 改名后 "Trigger" 一词只指 Trigger Entity 和 TriggerExecutor，不再作为 RPC 动词
- 保留在 `DagService` 符合职责划分（管理 DAG 生命周期）
- 替代方案 A/B 让用户"发事件"而非"跑 DAG"，间接且反直觉

**影响**：
- Proto：`rpc Trigger` → `rpc Run`，`DagTriggerRequest` → `DagRunRequest`
- CLI：`edera dag trigger` → `edera dag run`
- BFF 路由：`/api/dags/{name}/trigger` → `/api/dags/{name}/run`
- 前端 mutation：`useRunDag` 保持不变（已经是 run 语义）

### D4: pipeline_runs.trigger 列改名为 source

**选择**：`dag_runs.trigger` → `dag_runs.source`，值格式为 `{"manual", "startup", "retry", "trigger:<name>"}`

**替代方案 A**：改名为 `initiated_by`  
**替代方案 B**：保留 `trigger` 列名，只改表名

**理由**：
- `source` 语义清晰：记录 run 的发起来源
- 避免与 Trigger Entity 混淆（`trigger` 列不是指向 Trigger Entity 的外键）
- 值格式 `trigger:<name>` 保留了 Trigger Entity 的审计信息
- `initiated_by` 过长且不常用

**影响**：
- 数据库：`dag_runs.trigger` 列改名
- Pydantic validator：更新合法值检查
- 代码：所有读写该列的地方改为 `source`

### D5: 消灭 PipelineService，按职责重组

**选择**：
- `DagService`：管理单个 DAG（Run/Stop/Retry/Status/Edit）
- `EventService`（新）：事件注入（Emit/CreateRepairTask）
- `SystemService`：全局系统控制（PauseScheduler/ResumeScheduler/SchedulerStatus）

**替代方案 A**：保留 `PipelineService` 作为全局 controller  
**替代方案 B**：合并到一个 `OrchestrationService`

**理由**：
- 当前 `PipelineService` 职责混乱（全局控制 + 单 DAG 操作 + 事件注入）
- 按职责划分后每个 service 语义清晰
- `SystemService` 已有 Health/Reload，扩展 scheduler 控制符合其定位
- `EventService` 独立后可扩展更多事件管理功能（event history、event replay）
- 替代方案 A 保留了混乱，替代方案 B 失去了对象抽象

**影响**：
- Proto：删除 `PipelineService`，新增 `EventService`
- Python：`pipeline_service.py` 拆分为 `event_service.py` 和 `system_service.py`（部分）
- CLI：`edera trigger emit` → `edera event emit`
- gRPC client：`grpc_client.pipeline` → `grpc_client.event`

### D6: Sub-DAG 的 run_id 独立性

**选择**：子 DAG 有独立的 `run_id`，通过 `node_runs.metadata.parent_run_id` 关联父 run

**替代方案**：子 DAG 共享父 run 的 `run_id`，用 scope 区分

**理由**：
- 当前设计已是独立 run（`parent_cycle_id` 字段存在）
- 独立 `run_id` 让子 DAG 可以独立查询、重试、观察
- 符合"子 DAG 作为节点嵌套执行"的黑盒语义
- 改名只需 `parent_cycle_id` → `parent_run_id`

**影响**：
- `node_runs.metadata` 中的 `parent_cycle_id` → `parent_run_id`
- `node_runs.metadata` 中的 `sub_dag_cycle_id` → `sub_dag_run_id`

### D7: dag_runs.source 值格式

**选择**：保留核心枚举 + 扩展格式 `trigger:<name>`

合法值：
- `manual`：用户手动触发（UI/CLI）
- `startup`：系统启动时自动运行
- `retry`：重试失败的 run
- `trigger:<trigger_name>`：由 Trigger Entity fire（如 `trigger:morning-cron`）

**替代方案**：完全自由字符串，允许 `api:<client_id>` 等未来扩展

**理由**：
- 保留核心枚举便于查询和统计
- `trigger:<name>` 格式提供审计信息（能看到是哪个 trigger fire 的）
- 查询方便：`WHERE source LIKE 'trigger:%'` 找所有 trigger 启动的 run
- 向后兼容：现有的 "manual"/"startup"/"retry" 不变
- 未来扩展：可以添加新前缀（如 `api:<client>`、`webhook:<source>`）

**影响**：
- Pydantic validator：从固定枚举改为正则校验
- TriggerExecutor：fire 时写入 `trigger:<trigger.id>`
- 文档：在 GLOSSARY.md 中明确值格式约定

## Risks / Trade-offs

**[Risk] Proto breaking change 导致客户端不兼容**  
→ **Mitigation**：项目处于开发阶段，只有 edera-web BFF 和 edera CLI 两个内部客户端，可同步更新。未来发布前需建立 proto 版本管理机制。

**[Risk] DB migration 失败导致数据丢失**  
→ **Mitigation**：开发阶段可清空数据库重建。如需保留数据，migration 脚本需充分测试，包括外键约束的删除和重建顺序。

**[Risk] 全局替换 cycle_id → run_id 可能遗漏边缘场景**  
→ **Mitigation**：使用 grep 全量搜索确认，重点检查字符串字面量（如日志、错误消息）、注释、文档。运行完整测试套件验证。

**[Risk] Service 重组后 RPC 路径变更，前端路由失效**  
→ **Mitigation**：BFF 层统一适配新的 gRPC service，前端 HTTP API 路径保持稳定（如 `/api/dags/{name}/run`）。前端只需更新 API client 的 proto 类型定义。

**[Risk] GLOSSARY.md 文档与代码不同步**  
→ **Mitigation**：在 CI 中添加术语一致性检查（如禁止新代码引入 `pipeline_runs`、`cycle_id` 等已废弃术语）。Code review 时强制检查术语使用。

**[Trade-off] 一次性 mega change 导致 PR 过大**  
→ **Accept**：术语统一必须原子完成，否则会出现"半统一"中间态（如部分代码用 run_id，部分用 cycle_id）。大 PR 通过充分的自动化测试和分层 review（proto → storage → service → CLI → frontend）来保证质量。

**[Trade-off] 文件重命名导致 git history 追踪困难**  
→ **Accept**：使用 `git log --follow` 可追踪重命名后的文件历史。重命名带来的长期收益（术语清晰）远大于短期的 history 追踪成本。
