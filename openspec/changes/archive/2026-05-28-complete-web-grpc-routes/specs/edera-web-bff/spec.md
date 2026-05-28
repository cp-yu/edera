## ADDED Requirements

### Requirement: BFF route handler 纯 gRPC 调用
`edera-web` 的所有 HTTP route handler MUST 通过 `GrpcClient` 调用 `edera-server`，MUST NOT 调用本地配置加载器、本地存储 repository 或本地 PipelineController。

#### Scenario: Graph 编辑 route 通过 gRPC
- **WHEN** 浏览器请求 `GET /api/graph/dag/{name}`
- **THEN** BFF SHALL 通过 `GrpcClient.graph_get_dag(name)` 调用 GraphService，将返回的 JSON 直接透传

#### Scenario: Config 读写 route 通过 gRPC
- **WHEN** 浏览器请求 `PUT /api/config/system` 携带 TOML 内容
- **THEN** BFF SHALL 通过 `GrpcClient.config_save_system(content)` 调用 ConfigService，将返回结果透传

#### Scenario: Query route 通过 gRPC
- **WHEN** 浏览器请求 `GET /api/results`
- **THEN** BFF SHALL 通过 `GrpcClient.query_results_summary(...)` 调用 QueryService，将返回结果透传

#### Scenario: Pipeline 控制 route 通过 gRPC
- **WHEN** 浏览器请求 `POST /api/pipeline/dag/{name}/retry`
- **THEN** BFF SHALL 通过 `GrpcClient.pipeline_dag_retry(...)` 调用 PipelineService，将返回结果透传

### Requirement: BFF 不再 import 业务模块
`edera-web` 的 route handler 模块 MUST NOT import `edera_core.config.*`、`edera_core.storage.*`、`edera_core.pipeline.*` 中的任何符号。

#### Scenario: routes.py 不 import config 模块
- **WHEN** 检查 `packages/core/src/edera_core/web/routes.py` 的 import 列表
- **THEN** 文件 MUST NOT import `edera_core.config.editor`、`edera_core.config.entities`、`edera_core.config.loader`、`edera_core.config.schema`

#### Scenario: routes.py 不 import storage 模块
- **WHEN** 检查 `packages/core/src/edera_core/web/routes.py` 的 import 列表
- **THEN** 文件 MUST NOT import `edera_core.storage.repository`

#### Scenario: routes.py 不 import pipeline 模块
- **WHEN** 检查 `packages/core/src/edera_core/web/routes.py` 的 import 列表
- **THEN** 文件 MUST NOT import `edera_core.pipeline`

### Requirement: BFF deps.py 仅暴露 gRPC client
`edera-web` 的 `deps.py` MUST 只提供 `grpc_client()` 和 `error_response()` 两个 helper，MUST NOT 包含 `controller()`、`config_dir()`、`handler_registry()` 等本地资源访问函数。

#### Scenario: deps.py 函数集合
- **WHEN** 检查 `packages/core/src/edera_core/web/deps.py`
- **THEN** 文件 SHALL 仅 export `grpc_client` 和 `error_response`
- **AND** MUST NOT 定义 `controller`、`config_dir`、`handler_registry` 函数

#### Scenario: 无 501 fail-closed stub
- **WHEN** 检查 deps.py 函数实现
- **THEN** 文件 MUST NOT 包含返回 HTTP 501 的占位函数
