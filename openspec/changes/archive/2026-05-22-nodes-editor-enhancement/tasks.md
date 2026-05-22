## 1. Actions

- [x] A1 新增 `useHandler` query hook 和 `useSaveHandler` mutation hook（`frontend/src/api/queries.ts` 和 `mutations.ts`）
- [x] A2 重构 `NodesPage.tsx`：节点管理页新增与 LLM 节点、Function 节点、Skills 同级的 Handler tab
- [x] A3 顶层 Handler tab 调用 `useHandler` 加载 Function 节点 handler 代码，保存时调用 `useSaveHandler`
- [x] A4 `Inspector.tsx` 中 `PermissionConfigurator` 接收过滤后的 `entityTypes`：从 `formValues.entities` 提取 type 集合，过滤 `dag.entity_types`
- [x] A5 entities 变更时清理失效的 permission overrides：当某 type 不再被引用时，从 `formValues.entity_permissions` 中移除该 type

## 2. Checks

- [x] C1 验证 handler API hook 可用
  - Covers: A1
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 编译通过，无类型错误

- [x] C2 验证节点管理页展示顶层 Handler tab
  - Covers: A2, A3
  - Evidence: 浏览器访问 `/nodes` 页面
  - Expect: 页面顶部显示"Handler" tab，Function 节点卡片内部不显示"配置/Handler"子 tab

- [x] C3 验证 Handler 代码保存
  - Covers: A3
  - Evidence: 在顶层 Handler tab 修改代码后 blur，检查 `handlers/{name}.py` 文件内容
  - Expect: 文件内容与编辑器中修改后的代码一致

- [x] C4 验证权限配置器仅展示已选 entity type
  - Covers: A4
  - Evidence: 浏览器访问 `/workbench`，选中节点，在 EntitySelector 中仅选择 `stock` 类型的实体
  - Expect: PermissionConfigurator 仅展示 `stock` type 的权限字段，不展示其他 type

- [x] C5 验证取消选择 entity 后清理 permissions
  - Covers: A5
  - Evidence: 先为 `stock` type 添加权限覆盖，然后取消选择所有 stock 实体
  - Expect: `stock` type 的权限覆盖被自动清除，PermissionConfigurator 中不再显示该 type

- [x] C6 验证整体编译通过
  - Covers: A1, A2, A3, A4, A5
  - Command: `cd frontend && npx tsc --noEmit`
  - Expect: 零错误
