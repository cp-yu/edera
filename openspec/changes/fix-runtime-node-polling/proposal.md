## Why

DAG 运行期间，节点状态不会实时更新。`useRuntimeStatus` 查询仅在组件挂载时执行一次，缺少轮询机制，导致用户无法在运行过程中观察各节点的执行进度。

## What Changes

- `useRuntimeStatus` 在 DAG 运行期间启用 `refetchInterval` 轮询（2s）
- 运行结束后自动停止轮询

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `pipeline-control`: 运行时状态展示需支持实时轮询，运行期间前端 SHALL 以固定间隔刷新节点状态

## Impact

- 前端 `src/api/queries.ts`：`useRuntimeStatus` 添加条件轮询参数
- 前端 `src/features/workbench/WorkbenchPage.tsx`：传递 `isRunning` 给 `useRuntimeStatus`
