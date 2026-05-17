## 1. Actions

- [ ] A1 修改 `useRuntimeStatus` 接受 `polling` 参数，启用条件 `refetchInterval: polling ? 2000 : false`
- [ ] A2 修改 `WorkbenchPage` 将 `isRunning` 传递给 `useRuntimeStatus`

## 2. Checks

- [ ] C1 验证 `useRuntimeStatus` 支持条件轮询
  - Covers: A1
  - Evidence: 代码审查 `frontend/src/api/queries.ts` 中 `useRuntimeStatus` 函数签名和 `refetchInterval` 配置
  - Expect: 函数接受 `polling?: boolean` 参数，`refetchInterval` 值为 `polling ? 2000 : false`

- [ ] C2 验证 `WorkbenchPage` 正确传递轮询参数
  - Covers: A2
  - Evidence: 代码审查 `frontend/src/features/workbench/WorkbenchPage.tsx` 中 `useRuntimeStatus` 调用
  - Expect: 调用形式为 `useRuntimeStatus(isRunning)` 或等价传参方式
