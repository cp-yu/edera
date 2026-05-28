## Why

`edera-web-bff` spec 已声明"所有数据操作 MUST 通过 gRPC 调用 edera-server"，但当前实现中 ~85% 的 HTTP route 因缺少对应 gRPC RPC 而返回 501。Web Console 首页（Results）、Graph Editor、Config Editor、Entities 管理等核心页面全部不可用。需要在 server 端补齐 gRPC service 并将验证逻辑下沉，使 BFF 成为纯 HTTP→gRPC 映射层。

## What Changes

- 在 `proto/edera.proto` 新增 4 个 gRPC service：`GraphService`、`ConfigService`、`QueryService`、`PipelineService`
- 在 `edera-server` 实现对应 servicer，承载全部验证逻辑（config schema 校验、级联删除、EntityStore 操作、DB 查询）
- 在 `GrpcClient` 新增对应 wrapper 方法
- 重写 BFF `routes.py`：移除所有 `config_dir()`/`controller()`/`handler_registry()` 依赖，每个 route handler 变为纯 gRPC 调用 + JSON 转换
- 移除 BFF 对 `edera_core.config.*`、`edera_core.storage.repository`、`edera_core.pipeline` 的 import 依赖
- RPC payload 策略：RPC 签名 typed（明确的 operation + 关键标识字段），复杂请求/响应体使用 JSON string field

## Capabilities

### New Capabilities
- `grpc-graph-service`: gRPC GraphService，覆盖 DAG/Node-type/Skill/Handler 的完整 CRUD，验证逻辑在 server 端执行
- `grpc-config-service`: gRPC ConfigService，覆盖 system config、entity-types config 的读写，验证逻辑在 server 端执行
- `grpc-query-service`: gRPC QueryService，覆盖 briefings/advices/results/sources health/source logs/node-outputs/history 等 DB 查询
- `grpc-pipeline-service`: gRPC PipelineService，覆盖 pipeline run/pause/resume/stop、dag stop/retry、runtime-status 等控制面操作

### Modified Capabilities
- `edera-server-grpc`: 注册 4 个新 service 到 gRPC server，扩展 proto 文件
- `edera-web-bff`: 完整实现"配置无知契约"——所有 route 通过 gRPC，BFF 不再 import config/storage/pipeline 模块

## Impact

- `proto/edera.proto`：新增 ~30 RPC 定义和对应 message
- `packages/core/src/edera_core/server.py`：新增 4 个 servicer class，承载从 routes.py 迁移的验证/查询逻辑
- `packages/core/src/edera_core/grpc_client.py`：新增 ~30 个 wrapper 方法
- `packages/core/src/edera_core/web/routes.py`：重写为纯 gRPC 调用层（~1700 行→~400 行）
- `packages/core/src/edera_core/web/deps.py`：移除 501 stub，仅保留 `grpc_client()` 和 `error_response()`
- `packages/core/pyproject.toml`：BFF 入口不再需要 config/storage 相关依赖（但因共享包暂不拆分）
- **BREAKING**：移除 BFF 进程内直连模式（不再支持无 edera-server 独立运行 edera-web）
