## 1. Actions

- [x] A1 创建 GLOSSARY.md 术语表文档
- [x] A2 重命名 proto service 和 message（PipelineService → DagService/EventService/SystemService，DagTriggerRequest → DagRunRequest，cycle_id → run_id）
- [x] A3 重新生成 proto Python 代码（edera_pb2.py、edera_pb2_grpc.py）
- [x] A4 创建 Alembic migration 脚本（表重命名、列重命名、外键重建）
- [x] A5 重命名 Python 类和函数（PipelineController → DagController，PipelineRun → DagRun，create_pipeline_run → create_dag_run 等）
- [x] A6 重命名 Python 文件（pipeline.py → dag_controller.py，pipeline_service.py 拆分为 event_service.py 和 system_service.py 部分）
- [x] A7 全局替换代码中的 cycle_id → run_id（Python、TypeScript）
- [x] A8 更新 storage repository 函数（current_pipeline_run → current_dag_run 等）
- [x] A9 重组 gRPC service 实现（拆分 PipelineService 到 DagService/EventService/SystemService）
- [x] A10 更新 CLI 子命令（dag trigger → dag run，trigger emit → event emit，新增 system pause-scheduler/resume-scheduler/scheduler-status）
- [x] A11 更新 gRPC client（grpc_client.pipeline → grpc_client.event，适配新 service）
- [x] A12 更新 BFF HTTP 路由（适配新 gRPC service，响应中使用 run_id）
- [x] A13 更新 TypeScript 类型定义（cycle_id → run_id，PipelineRun → DagRun）
- [x] A14 更新前端 API mutations 和 queries（适配新的 proto 类型）
- [x] A15 更新 dag_runs.trigger 列为 source，更新 Pydantic validator 支持 trigger:<name> 格式
- [x] A16 更新 TriggerExecutor fire 逻辑，写入 source=trigger:<trigger.id>
- [x] A17 执行数据库 migration（开发环境可清空重建）
- [x] A18 更新所有测试用例中的术语（cycle_id → run_id，PipelineRun → DagRun 等）

## 2. Checks

- [x] C1 验证 GLOSSARY.md 包含核心概念定义
  - Covers: A1
  - Verifies: `specs/terminology-glossary/spec.md` / Requirement "术语表文档" / Scenario "核心概念定义"
  - Evidence: GLOSSARY.md 文件内容
  - Expect: 文档包含 DAG、Node、Edge、Run、run_id、Trigger Entity、TriggerExecutor、Emit、Source 的定义

- [x] C2 验证 GLOSSARY.md 标注禁用同义词
  - Covers: A1
  - Verifies: `specs/terminology-glossary/spec.md` / Requirement "术语表文档" / Scenario "禁用同义词标注"
  - Evidence: GLOSSARY.md 文件内容
  - Expect: DAG 条目明确标注 `~~Pipeline~~` 为禁用同义词

- [x] C3 验证 GLOSSARY.md 包含动词约定
  - Covers: A1
  - Verifies: `specs/terminology-glossary/spec.md` / Requirement "术语表文档" / Scenario "动词约定"
  - Evidence: GLOSSARY.md 文件内容
  - Expect: 文档包含动词约定表，定义"手动运行 DAG"、"注入事件"等对应的 API/CLI 命令

- [x] C4 验证 proto 定义 EventService
  - Covers: A2, A3
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "EventService 提供事件注入"
  - Command: `grep -n "service EventService" proto/edera.proto`
  - Expect: proto 文件包含 EventService 定义

- [x] C5 验证 proto 定义 DagService.Run
  - Covers: A2, A3
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "DagService 提供运行和查询"
  - Command: `grep -n "rpc Run" proto/edera.proto`
  - Expect: DagService 包含 Run RPC，不再有 Trigger RPC

- [x] C6 验证 proto 定义 SystemService scheduler 控制
  - Covers: A2, A3
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "SystemService 提供 scheduler 控制"
  - Command: `grep -n "rpc PauseScheduler\|rpc ResumeScheduler" proto/edera.proto`
  - Expect: SystemService 包含 PauseScheduler 和 ResumeScheduler RPC

- [x] C7 验证 DagRunRef 使用 run_id
  - Covers: A2, A3
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "DagRunRef 使用 run_id" / Scenario "DagRunRef 字段定义"
  - Command: `grep -n "message DagRunRef" -A 3 proto/edera.proto`
  - Expect: DagRunRef message 包含 `string run_id = 1;`，不包含 cycle_id

- [x] C8 验证 proto 不包含 PipelineService
  - Covers: A2, A3
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "EventService 注册到 server"
  - Command: `grep -n "service PipelineService" proto/edera.proto`
  - Expect: 无匹配结果（PipelineService 已删除）

- [x] C9 验证数据库表重命名
  - Covers: A4, A17
  - Verifies: `specs/data-models/spec.md` / Requirement "数据库迁移" / Scenario "表重命名"
  - Command: `sqlite3 edera.db ".tables" | grep dag_runs`
  - Expect: 存在 dag_runs 表，不存在 pipeline_runs 表

- [x] C10 验证数据库列重命名
  - Covers: A4, A17
  - Verifies: `specs/data-models/spec.md` / Requirement "数据库迁移" / Scenario "列重命名"
  - Command: `sqlite3 edera.db ".schema dag_runs" | grep run_id`
  - Expect: dag_runs 表包含 run_id 列，不包含 cycle_id 列

- [x] C11 验证 dag_runs.source 列存在
  - Covers: A4, A15, A17
  - Verifies: `specs/data-models/spec.md` / Requirement "数据库迁移" / Scenario "列重命名"
  - Command: `sqlite3 edera.db ".schema dag_runs" | grep source`
  - Expect: dag_runs 表包含 source 列，不包含 trigger 列

- [x] C12 验证 DagRun 类定义
  - Covers: A5
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "创建 DagRun 记录"
  - Command: `grep -n "class DagRun" packages/core/src/edera_core/storage/entities.py`
  - Expect: 存在 DagRun 类定义，不存在 PipelineRun 类

- [x] C13 验证 DagController 类定义
  - Covers: A5, A6
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "edera-web 纯 BFF 角色" / Scenario "不实例化 controller"
  - Command: `grep -n "class DagController" packages/core/src/edera_core/dag_controller.py`
  - Expect: 存在 DagController 类定义，文件名为 dag_controller.py

- [x] C14 验证 EventService 实现
  - Covers: A9
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "EventService 注册到 server"
  - Command: `grep -n "class.*EventService" packages/core/src/edera_core/event_service.py`
  - Expect: 存在 EventService 实现类

- [x] C15 验证 CLI dag run 子命令
  - Covers: A10
  - Verifies: `specs/edera-cli/spec.md` / Requirement "DAG 子命令" / Scenario "DAG 手动运行"
  - Command: `edera dag run --help`
  - Expect: 输出包含 run 子命令帮助信息

- [x] C16 验证 CLI event emit 子命令
  - Covers: A10
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Event 子命令" / Scenario "事件注入"
  - Command: `edera event emit --help`
  - Expect: 输出包含 emit 子命令帮助信息

- [x] C17 验证 CLI system pause-scheduler 子命令
  - Covers: A10
  - Verifies: `specs/edera-cli/spec.md` / Requirement "System 子命令" / Scenario "暂停 scheduler"
  - Command: `edera system pause-scheduler --help`
  - Expect: 输出包含 pause-scheduler 子命令帮助信息

- [x] C18 验证 CLI 不包含 dag trigger 子命令
  - Covers: A10
  - Verifies: `specs/edera-cli/spec.md` / Requirement "DAG 子命令" / Scenario "DAG 手动运行"
  - Command: `edera dag trigger --help 2>&1`
  - Expect: 输出错误信息（子命令不存在）

- [x] C19 验证 gRPC client 包含 event 属性
  - Covers: A11
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "gRPC client 适配新 service" / Scenario "调用 EventService.Emit"
  - Command: `grep -n "self.event" packages/core/src/edera_core/grpc_client.py`
  - Expect: GrpcClient 包含 event 属性（EventServiceStub）

- [x] C20 验证 BFF 路由返回 run_id
  - Covers: A12
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "响应中使用 run_id" / Scenario "DAG 状态响应"
  - Command: `grep -n "run_id" packages/core/src/edera_core/web/routes.py`
  - Expect: BFF 路由返回的 JSON 包含 run_id 字段

- [x] C21 验证 TypeScript 类型定义使用 run_id
  - Covers: A13
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "响应中使用 run_id" / Scenario "节点历史响应"
  - Command: `grep -n "run_id" apps/web-console/src/api/types.ts`
  - Expect: TypeScript 类型定义包含 run_id 字段，不包含 cycle_id

- [x] C22 验证 source 字段 validator 支持 trigger:<name>
  - Covers: A15
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "source 字段合法值"
  - Command: `grep -n "_valid_source\|_valid_trigger" packages/core/src/edera_core/storage/entities.py`
  - Expect: validator 支持 manual、startup、retry、trigger:<name> 格式

- [x] C23 验证 TriggerExecutor fire 写入 source
  - Covers: A16
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "Trigger Entity fire 时记录 source"
  - Command: `grep -n "trigger:" packages/core/src/edera_core/trigger.py`
  - Expect: TriggerExecutor fire 时写入 source=trigger:<trigger.id>

- [x] C24 验证代码中无 cycle_id 残留
  - Covers: A7, A18
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "创建 DagRun 记录"
  - Command: `grep -rn "cycle_id" packages/core/src/edera_core/ --include="*.py" | grep -v "# legacy\|migration" | wc -l`
  - Expect: 无匹配结果（除了 migration 和注释）

- [x] C25 验证代码中无 PipelineRun 残留
  - Covers: A5, A18
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "创建 DagRun 记录"
  - Command: `grep -rn "PipelineRun" packages/core/src/edera_core/ --include="*.py" | grep -v "migration" | wc -l`
  - Expect: 无匹配结果（除了 migration）

- [x] C26 验证 DAG 手动运行返回 run_id
  - Covers: A2, A3, A9, A10, A11, A12
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "DagRunRef 使用 run_id" / Scenario "DagService.Run 返回 run_id"
  - Command: `edera dag run default --inputs '{}' | jq .run_id`
  - Expect: 输出 UUID 格式的 run_id

- [x] C27 验证事件注入功能
  - Covers: A2, A3, A9, A10, A11
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Event 子命令" / Scenario "事件注入"
  - Command: `edera event emit test-event --payload '{"test": true}'`
  - Expect: 命令执行成功，无错误输出

- [x] C28 验证 scheduler 暂停恢复功能
  - Covers: A2, A3, A9, A10
  - Verifies: `specs/edera-cli/spec.md` / Requirement "System 子命令" / Scenario "暂停 scheduler"
  - Command: `edera system pause-scheduler && edera system scheduler-status`
  - Expect: 状态显示 scheduler 已暂停

- [x] C29 验证完整测试套件通过
  - Covers: A18
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "创建 DagRun 记录"
  - Command: `pytest packages/core/tests/`
  - Expect: 所有测试通过，无失败用例
