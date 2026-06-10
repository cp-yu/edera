## Why

`edera` CLI 已覆盖核心执行入口，但 GraphService、ConfigService、QueryService 的控制面能力仍主要停留在 Web BFF 或 `GrpcClient` 封装层，脚本和 agent 无法通过统一 CLI 完成 DAG 定义、配置、handler、runtime 查询和结果查询。

## What Changes

- 扩展 `edera dag`，增加 DAG 定义层的 `list`、`show`、`create`、`save`、`export`、`import` 和 `runtime-status` 命令。
- 新增 `edera node-type` 命令组，覆盖 node type 的 `list`、`show`、`create`、`save`、`delete`。
- 新增 `edera handler` 命令组，覆盖 handler 的 `list`、`show`、`save`，继续保留 `handler-validate` 作为离线校验工具。
- 新增 `edera config` 命令组，覆盖 config 文件列表、system config 读写、通用 config 读写、entity type config CRUD。
- 新增 `edera query` 命令组，覆盖 briefing、advice、results summary、node outputs、node history、child run 查询。
- 新增 `edera source` 命令组，覆盖 source health、source logs 和 source repair task 创建。
- 不新增 gRPC RPC，不改变 Web BFF API；CLI 只复用现有 `GrpcClient` 方法和 server 端校验。

## Capabilities

### New Capabilities
- `edera-cli-control-plane`: 覆盖 `edera` CLI 对 GraphService、ConfigService、QueryService 和 source 运维能力的脚本化控制面入口。

### Modified Capabilities
- `edera-cli`: 顶层 CLI 子命令集合增加 `config`、`query`、`source`、`handler`、`node-type`，并扩展 `dag` 定义管理命令。

## Impact

- Affected code: `packages/core/src/edera_core/cli.py`, `packages/core/src/edera_core/grpc_client.py`, `tests/core/unit/test_cli.py`。
- Affected specs: `openspec/specs/edera-cli/spec.md`, new `openspec/specs/edera-cli-control-plane/spec.md` after archive.
- Affected OPSX: `cap.core.edera-cli` depends on `cap.core.grpc-graph-service`, `cap.core.grpc-config-service`, `cap.core.grpc-query-service`, `cap.core.grpc-control-services`, and `cap.web.source-health-monitoring` for the newly exposed command groups.
- No database schema, protobuf, server API, Web BFF API, or frontend behavior changes are expected.
