<!--
Smart routing decision:
- Design Summary found: yes
- Input length: >100 characters from confirmed explore summary
- Detail score: 5/5
- Multi-subsystem: yes, but proceeding because Design Summary exists
- Decision: use the confirmed Design Summary as primary input
-->
## Why

当前 Runtime/History 视图把业务输出和执行可观测混在一起：节点失败、成功但无 payload、或 agent 失败时，用户经常只能看到“暂无输出”，无法确认节点是否执行过以及执行过程留下了什么。需要明确“已执行节点必有可查询日志”的契约，同时保持 `node_outputs` 只承载真实业务产物。

## What Changes

- 为每个实际开始执行的 node run 记录系统生成的执行摘要日志，覆盖成功、失败、空 payload、wait timeout、agent 成功/失败等路径。
- 保持 `NodeOutputEntity` 只表示真实业务输出；失败和空 payload 不伪造成业务 output。
- agent stdout 继续实时推送，并纳入可查询执行日志语义；大日志继续通过 raw log file + `log_index` 索引。
- BFF/API、Web Runtime tab、Node History 和 CLI 增加执行日志查询/展示面。
- 未被调度执行的节点（例如 required 上游失败导致未启动）不要求输出或日志。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dag-run-observability`: 合并节点执行日志、agent stdout 历史、log index 边界和 Runtime/History 展示契约；已执行节点 SHALL 有 execution logs，业务 output 与日志保持分离。
- `edera-web-bff`: BFF SHALL 通过 gRPC 暴露节点执行日志查询，并保持 HTTP route 纯 gRPC 转发。
- `edera-cli`: `edera node` SHALL 提供按 `run_id` 查看节点执行日志的能力。

## Impact

- 后端执行路径：`packages/core/src/edera_core/node/executor.py`、`packages/core/src/edera_core/dag/runner.py`、`packages/core/src/edera_core/dag_controller.py`
- 持久化与查询：`packages/core/src/edera_core/storage/entities.py`、`packages/core/src/edera_core/storage/repository.py`、`packages/core/src/edera_core/query_service.py`
- API/BFF/CLI：`proto/edera.proto`、`packages/core/src/edera_core/grpc_client.py`、`packages/core/src/edera_core/web/routes.py`、`packages/core/src/edera_core/cli.py`
- 前端：`apps/web-console/src/features/workbench/components/Inspector.tsx`、`apps/web-console/src/features/history/NodeHistoryPage.tsx`、`apps/web-console/src/api/*`
- 测试：`tests/core/unit/test_node_executor.py`、`tests/core/integration/test_dag_runner.py`、Web route/API tests、Workbench UI tests
