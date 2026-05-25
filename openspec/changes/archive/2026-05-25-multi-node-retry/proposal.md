## Why

当前 retry API 仅支持单节点重试。用户在 DAG 画布上排查问题时，常需要批量重试一组节点（如一条失败路径上的多个节点），目前只能逐个右键操作，效率低且容易遗漏。

## What Changes

- 将 `POST /api/pipeline/dag/{dag_name}/retry` 的 `node_id` 参数替换为 `node_ids: string[]`，支持多节点批量重试
- `cycle_id` 变为可选参数，不传时默认取该 DAG 最近一次非 running 的 run
- `single` 模式语义：选中节点集合作为 mini sub-DAG 执行，内部按拓扑序传播新结果，外部输入用 prefilled
- `cascade` 模式语义：各节点 downstream 取并集
- API 响应增加 `retry_nodes` 字段，返回实际执行的完整节点集合
- 前端支持框选/Ctrl+多选节点后右键触发批量重试

## Capabilities

### New Capabilities

- `multi-node-retry`: 多节点批量重试能力，覆盖 API 参数泛化、多起点拓扑调度、prefilled 数据加载和前端批量选择交互

### Modified Capabilities

- `dag-run-control`: 扩展节点重试 requirement，从单节点泛化到多节点

## Impact

- 后端：`packages/core/src/stockimformation_core/pipeline.py` 的 `retry_node` 方法签名变更
- 后端：`packages/core/src/stockimformation_core/web/routes.py` 的 retry endpoint 参数变更
- 前端：`apps/web-console/src/api/mutations.ts` 的 `useRetryDagNode` mutation 参数变更
- 前端：`apps/web-console/src/features/workbench/components/Canvas.tsx` 右键菜单逻辑扩展
- 前端：`apps/web-console/src/api/types.ts` 类型定义更新
