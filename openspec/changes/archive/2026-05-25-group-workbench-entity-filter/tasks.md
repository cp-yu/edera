## 1. Actions

- [x] A1 将底部 `EntityFilter` 改为紧凑的分组多选控件。
- [x] A2 增加 Workbench 前端验收测试，覆盖分组展示、多选和清除。

## 2. Checks

- [x] C1 验证分组 entity 过滤交互
  - Covers: A1, A2
  - Command: `npx playwright test --project=chrome tests/workbench-entity-filter.spec.ts`
  - Expect: 测试通过，证明底栏显示摘要、展开后按 type 分组、多选和清除均可用。

- [x] C2 验证 Web 构建
  - Covers: A1
  - Command: `npm run build`
  - Expect: TypeScript 和 Vite 构建通过。
