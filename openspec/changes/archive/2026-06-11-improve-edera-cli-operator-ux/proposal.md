## Why

前两阶段已经补齐 CLI 的核心缺口和控制面入口，但输出仍固定为 JSON，长列表缺少统一分页，运行观察缺少 watch/tail 模式，脚本和人工排障都需要重复包装命令。现在需要把这些 operator UX 收敛到 CLI 层，避免每个命令各自发明格式、轮询和错误展示。

## What Changes

- 为 CLI 增加统一输出模式，支持 `--output json|yaml|table`，默认保持现有 JSON 行为。
- 为列表型 query/source/config/graph 命令增加统一 `--limit`/`--offset` 展示边界；已有 server limit 继续下传，offset 作为 CLI 只读展示裁剪。
- 为运行观察命令增加 `--watch` 和 `--interval`，覆盖 `dag status`、`dag runtime-status`、`system scheduler-status`、`source health`。
- 为日志类命令增加 `--tail`，覆盖 `node logs`、`source logs`，按固定间隔追加显示新增结果。
- 统一 CLI 错误输出结构，保持 stderr 和非零退出，不改变 server 校验来源。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `edera-cli`: 增加全局输出模式、watch/tail 行为和统一错误输出要求。
- `edera-cli-control-plane`: 增加控制面列表查询的分页参数和 operator-friendly 输出要求。

## Impact

- 代码：`packages/core/src/edera_core/cli.py`、必要时 `packages/core/src/edera_core/grpc_client.py`。
- 测试：`tests/core/unit/test_cli.py`。
- OpenSpec：修改 `edera-cli` 和 `edera-cli-control-plane` 的 delta specs，新增实现任务。
- 不新增 protobuf RPC、数据库表、Web BFF route 或前端页面。
