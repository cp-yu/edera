## Why

`edera` CLI 是人类和 agent 访问控制面的统一入口。本阶段完善运行控制命令入口，使脚本化运维和 agent runtime 操作可以通过 CLI 完成。

## What Changes

- 新增 `edera node output export --run-id <run_id> --node <node_id> --out <path>`，用于 agent 显式导出上游 payload。
- 扩展 `edera dag retry`，支持 `--source-shared-inputs`、`--node-inputs`、`--append-nodes` 临时输入参数。
- 为已存在的 `SystemService.CreateRepairTask` 增加 CLI 入口，允许为 escalated source 创建 repair task。
- 对齐 `edera extension export` 的 workflow extension 打包契约，确保 providers 和 libraries 的导出结构满足规格。

## Capabilities

### New Capabilities

### Modified Capabilities
- `edera-cli`: 新增 node output export、dag retry 临时输入、system source repair task 和 extension export 的 CLI 行为。
- `multi-node-retry`: 明确 CLI retry 路径传递临时输入参数。
- `runtime-input-context`: 将已记录的 agent payload export 命令落到可执行 CLI 行为。
- `extension-cli-commands`: 收紧 workflow extension export 的 providers 和 libraries 打包要求。
- `grpc-control-services`: 将 source repair task 的 gRPC 能力暴露到 `edera system` CLI。

## Impact

- 代码：`packages/core/src/edera_core/cli.py`、`packages/core/src/edera_core/grpc_client.py`。
- 测试：`tests/core/unit/test_cli.py`、`tests/core/unit/test_cli_extension.py`。
- 规格：复用并修改现有 CLI、retry、runtime input、extension CLI、control services specs。
- 不涉及服务端 RPC schema 变更；优先复用已有 `GrpcClient` 和 gRPC service 方法。
