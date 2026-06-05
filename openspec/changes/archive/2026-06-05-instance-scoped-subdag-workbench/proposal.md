<!-- propose routing: Design Summary from prior explore used. inputLength=17, detailScore=5/5 via conversation context, multiSubsystem=true, decision=proceed because user explicitly invoked $openspec-propose after explore. -->
## Why

Workbench 目前只能在 DAG 选择器中切换 DAG，不能从父 DAG 的 sub-DAG 节点进入对应子图；同时 DAG 也没有作为可拖入节点出现在左侧节点面板中。更严重的是，同一个子 DAG 被多个父 DAG 或多个父节点实例复用时，单纯按 `dag_name` 查看运行状态会串线，无法展示“这个父节点实例触发的 child run”。

## What Changes

- 左侧节点面板 SHALL 将 DAG 列为可拖入的节点候选，拖入后创建保留 `dag_ref` 的 sub-DAG 节点实例。
- Workbench graph GET/SAVE round-trip SHALL 保留 `DagNodeInstance.dag_ref` 和 `input_mapping`。
- 节点右键菜单 SHALL 仅对可解析目标 DAG 的 sub-DAG 节点显示“进入 Sub DAG”。
- 进入 Sub DAG SHALL 建立实例作用域上下文：父 DAG、父节点实例、父 run、child run 和目标 DAG。
- Runtime status SHALL 支持按指定 `run_id` 查询，进入 sub-DAG 实例后只展示对应 child run 的节点状态。
- 保留现有根 DAG 选择、节点历史、运行、重试、删除和连线编辑行为。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `dag-workbench-ui`: 左侧节点面板展示 DAG 候选，并支持实例作用域 sub-DAG 面包屑/返回导航。
- `canvas-interaction-enhancement`: sub-DAG 节点右键菜单增加“进入 Sub DAG”，且菜单行为绑定父节点实例。
- `dag-run-observability`: Runtime 视图按实例 child run 展示子 DAG 内部节点状态，避免同名子 DAG 的状态串线。
- `grpc-graph-service`: GraphService DAG payload 保留 `dag_ref/input_mapping`，runtime-status 支持 run_id-scoped 查询。
- `node-instance-model`: DAG 节点实例格式保留 `dag_ref/input_mapping`，支持多实例引用同一 DAG。
- `sub-dag-execution`: 子 DAG 执行记录必须可从父节点实例解析到 child run。

## Impact

- 前端：`apps/web-console/src/api/types.ts`、`apps/web-console/src/api/queries.ts`、`apps/web-console/src/store/useAppStore.ts`、`apps/web-console/src/features/workbench/**`。
- 后端/BFF：`packages/core/src/edera_core/graph_service.py`、`packages/core/src/edera_core/service_common.py`、`packages/core/src/edera_core/grpc_client.py`、`packages/core/src/edera_core/web/routes.py`、必要时 `proto/edera.proto`。
- 测试：`packages/core/tests/test_graph_service.py`、`packages/core/tests/test_web_routes.py`、`apps/web-console/tests/workbench-usability.spec.ts` 或新增 Workbench Playwright 用例。
