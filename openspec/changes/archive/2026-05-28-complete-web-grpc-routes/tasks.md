## 1. Actions

- [x] A1 在 `proto/edera.proto` 增加 `GraphService`、`ConfigService`、`QueryService`、`PipelineService` 定义和对应 message
- [x] A2 执行 `scripts/gen_proto.sh` 重生成 `packages/core/src/edera_core/proto/edera_pb2*.py` 并提交
- [x] A3 在 `packages/core/src/edera_core/query_service.py` 实现 `_QueryService` servicer，承载 briefings/advices/results/sources/node-outputs/history 查询逻辑
- [x] A4 在 `packages/core/src/edera_core/pipeline_service.py` 实现 `_PipelineService` servicer，承载 pipeline run/pause/resume/stop、dag stop/retry、source repair task 逻辑
- [x] A5 在 `packages/core/src/edera_core/graph_service.py` 实现 `_GraphService` servicer，承载 DAG/node-type/skill/handler CRUD 和 runtime-status 逻辑
- [x] A6 在 `packages/core/src/edera_core/config_service.py` 实现 `_ConfigService` servicer，承载 system config 和 entity-types CRUD 逻辑
- [x] A7 在 `packages/core/src/edera_core/server.py` 的 `_add_services` 注册 4 个新 servicer
- [x] A8 在 `packages/core/src/edera_core/grpc_client.py` 增加 4 个 service stub 与 ~30 个 wrapper 方法
- [x] A9 重写 `packages/core/src/edera_core/web/routes.py`，所有 handler 改为纯 `grpc_client(...)` 调用
- [x] A10 精简 `packages/core/src/edera_core/web/deps.py`，仅保留 `grpc_client` 和 `error_response`
- [x] A11 移除 `routes.py` 对 `edera_core.config.*`、`edera_core.storage.*`、`edera_core.pipeline` 的 import

## 2. Checks

- [x] C1 验证 proto 文件包含 4 个新 service 定义
  - Covers: A1
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "GraphService 注册到 server" / Scenario "ConfigService 注册到 server" / Scenario "QueryService 注册到 server" / Scenario "PipelineService 注册到 server"
  - Command: `grep -E "service (GraphService|ConfigService|QueryService|PipelineService)" proto/edera.proto`
  - Expect: 输出包含 4 个 service 行

- [x] C2 验证 pb2 文件已重新生成且包含新 service stub
  - Covers: A2
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "GraphService 注册到 server"
  - Command: `python -c "from edera_core.proto import edera_pb2_grpc; assert hasattr(edera_pb2_grpc, 'GraphServiceStub') and hasattr(edera_pb2_grpc, 'ConfigServiceStub') and hasattr(edera_pb2_grpc, 'QueryServiceStub') and hasattr(edera_pb2_grpc, 'PipelineServiceStub')"`
  - Expect: 命令以 0 退出码返回

- [x] C3 验证 QueryService 查询 latest briefing 返回正确数据
  - Covers: A3
  - Verifies: `specs/grpc-query-service/spec.md` / Requirement "QueryService briefing 查询" / Scenario "查询最新 briefing"
  - Command: `pytest packages/core/tests/test_query_service.py -k latest_briefing`
  - Expect: 测试通过

- [x] C4 验证 QueryService 查询不存在 advice 返回 NOT_FOUND
  - Covers: A3
  - Verifies: `specs/grpc-query-service/spec.md` / Requirement "QueryService advice 查询" / Scenario "advice 不存在"
  - Command: `pytest packages/core/tests/test_query_service.py -k advice_not_found`
  - Expect: 测试通过且返回 grpc.StatusCode.NOT_FOUND

- [x] C5 验证 QueryService results 聚合查询返回完整字段
  - Covers: A3
  - Verifies: `specs/grpc-query-service/spec.md` / Requirement "QueryService results 聚合查询" / Scenario "查询 results summary"
  - Command: `pytest packages/core/tests/test_query_service.py -k results_summary`
  - Expect: 返回包含 briefing/briefings/advices/events/event_details/summary_items/metadata_bar/failed_sources 全部字段

- [x] C6 验证 PipelineService 启动 run 在已有活跃 run 时返回 ALREADY_EXISTS
  - Covers: A4
  - Verifies: `specs/grpc-pipeline-service/spec.md` / Requirement "PipelineService 全局 pipeline 控制" / Scenario "启动时已有活跃 run"
  - Command: `pytest packages/core/tests/test_pipeline_service.py -k run_already_active`
  - Expect: 测试通过且返回 grpc.StatusCode.ALREADY_EXISTS

- [x] C7 验证 PipelineService DAG retry 在 cycle 不存在时返回 NOT_FOUND
  - Covers: A4
  - Verifies: `specs/grpc-pipeline-service/spec.md` / Requirement "PipelineService DAG 级控制" / Scenario "重试时 cycle 不存在"
  - Command: `pytest packages/core/tests/test_pipeline_service.py -k retry_cycle_not_found`
  - Expect: 测试通过且返回 grpc.StatusCode.NOT_FOUND

- [x] C8 验证 PipelineService 创建 repair task 在 source 未 escalated 时拒绝
  - Covers: A4
  - Verifies: `specs/grpc-pipeline-service/spec.md` / Requirement "PipelineService source repair task" / Scenario "source 未 escalated"
  - Command: `pytest packages/core/tests/test_pipeline_service.py -k repair_task_not_escalated`
  - Expect: 测试通过且返回 grpc.StatusCode.FAILED_PRECONDITION

- [x] C9 验证 GraphService 保存非法 DAG 返回 INVALID_ARGUMENT
  - Covers: A5
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "保存非法 DAG"
  - Command: `pytest packages/core/tests/test_graph_service.py -k save_invalid_dag`
  - Expect: 测试通过且返回 grpc.StatusCode.INVALID_ARGUMENT

- [x] C10 验证 GraphService 删除被引用的 node type 返回 FAILED_PRECONDITION
  - Covers: A5
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService Node-type CRUD" / Scenario "删除被引用的 node type"
  - Command: `pytest packages/core/tests/test_graph_service.py -k delete_referenced_node_type`
  - Expect: 测试通过且返回 grpc.StatusCode.FAILED_PRECONDITION

- [x] C11 验证 GraphService 创建 skill 写入 YAML 和 handler.py
  - Covers: A5
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService Skill CRUD" / Scenario "创建 skill"
  - Command: `pytest packages/core/tests/test_graph_service.py -k create_skill`
  - Expect: 测试通过且 skills/{name}.yaml 和 extensions/{handler}/handler.py 均已写入

- [x] C12 验证 GraphService 获取 DAG 详情返回完整聚合数据
  - Covers: A5
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "获取 DAG 详情"
  - Command: `pytest packages/core/tests/test_graph_service.py -k get_dag_detail`
  - Expect: 返回 JSON 包含 nodes/edges/ui/entity_types/entities/entity_relations 全部字段

- [x] C13 验证 ConfigService 删除有实例无 cascade 的 entity type 返回 FAILED_PRECONDITION
  - Covers: A6
  - Verifies: `specs/grpc-config-service/spec.md` / Requirement "ConfigService entity-type CRUD" / Scenario "删除 entity type 有实例无 cascade"
  - Command: `pytest packages/core/tests/test_config_service.py -k delete_entity_type_no_cascade`
  - Expect: 测试通过且返回 grpc.StatusCode.FAILED_PRECONDITION

- [x] C14 验证 ConfigService 更新 system protected entity type 返回 PERMISSION_DENIED
  - Covers: A6
  - Verifies: `specs/grpc-config-service/spec.md` / Requirement "ConfigService entity-type CRUD" / Scenario "更新 system protected entity type"
  - Command: `pytest packages/core/tests/test_config_service.py -k save_system_protected`
  - Expect: 测试通过且返回 grpc.StatusCode.PERMISSION_DENIED

- [x] C15 验证 ConfigService 保存非法 system config 返回 INVALID_ARGUMENT
  - Covers: A6
  - Verifies: `specs/grpc-config-service/spec.md` / Requirement "ConfigService system config 读写" / Scenario "保存非法 system config"
  - Command: `pytest packages/core/tests/test_config_service.py -k save_invalid_system_config`
  - Expect: 测试通过且返回 grpc.StatusCode.INVALID_ARGUMENT

- [x] C16 验证 server.py 注册了 4 个新 servicer
  - Covers: A7
  - Verifies: `specs/edera-server-grpc/spec.md` / Requirement "gRPC Service 定义" / Scenario "GraphService 注册到 server" / Scenario "ConfigService 注册到 server" / Scenario "QueryService 注册到 server" / Scenario "PipelineService 注册到 server"
  - Command: `grep -E "add_(GraphService|ConfigService|QueryService|PipelineService)Servicer_to_server" packages/core/src/edera_core/server.py`
  - Expect: 输出包含 4 行注册调用

- [x] C17 验证 GrpcClient 暴露 4 个新 service stub
  - Covers: A8
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF route handler 纯 gRPC 调用" / Scenario "Graph 编辑 route 通过 gRPC" / Scenario "Config 读写 route 通过 gRPC" / Scenario "Query route 通过 gRPC" / Scenario "Pipeline 控制 route 通过 gRPC"
  - Command: `python -c "from edera_core.grpc_client import GrpcClient; import inspect; src = inspect.getsource(GrpcClient); assert 'GraphServiceStub' in src and 'ConfigServiceStub' in src and 'QueryServiceStub' in src and 'PipelineServiceStub' in src"`
  - Expect: 命令以 0 退出码返回

- [x] C18 验证 routes.py 所有 handler 不再依赖 controller/config_dir/handler_registry
  - Covers: A9
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF route handler 纯 gRPC 调用" / Scenario "Graph 编辑 route 通过 gRPC"
  - Command: `grep -E "(controller|config_dir|handler_registry)\(request\)" packages/core/src/edera_core/web/routes.py`
  - Expect: 无输出（grep 退出码 1）

- [x] C19 验证前端 Results 页通过 BFF 拿到聚合数据
  - Covers: A9
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF route handler 纯 gRPC 调用" / Scenario "Query route 通过 gRPC"
  - Command: `pytest packages/core/tests/test_web_routes.py -k results_summary_through_bff`
  - Expect: 测试通过且响应包含全部 results summary 字段

- [x] C20 验证 deps.py 仅 export grpc_client 和 error_response
  - Covers: A10
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF deps.py 仅暴露 gRPC client" / Scenario "deps.py 函数集合" / Scenario "无 501 fail-closed stub"
  - Command: `python -c "from edera_core.web import deps; assert hasattr(deps, 'grpc_client') and hasattr(deps, 'error_response') and not hasattr(deps, 'controller') and not hasattr(deps, 'config_dir') and not hasattr(deps, 'handler_registry')"`
  - Expect: 命令以 0 退出码返回

- [x] C21 验证 routes.py 不再 import config/storage/pipeline 模块
  - Covers: A11
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "BFF 不再 import 业务模块" / Scenario "routes.py 不 import config 模块" / Scenario "routes.py 不 import storage 模块" / Scenario "routes.py 不 import pipeline 模块"
  - Command: `grep -E "from edera_core\.(config|storage|pipeline)" packages/core/src/edera_core/web/routes.py`
  - Expect: 无输出（grep 退出码 1）
