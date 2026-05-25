## 1. Actions

- [x] A1 修改 `PipelineController.retry_node` 方法签名：`node_id: str` → `node_ids: list[str]`，计算 retry_nodes 为多节点并集
- [x] A2 `cycle_id` 可选化：不传时查询该 DAG 最近一次非 running 的 PipelineRun
- [x] A3 修改 `api_dag_retry` route handler：body 参数从 `node_id` 改为 `node_ids`，响应增加 `retry_nodes` 字段
- [x] A4 添加 prefilled 完整性校验：检查选中节点的外部上游是否在指定 cycle 中有可用 output，缺失时返回 400
- [x] A5 前端 `useRetryDagNode` mutation 参数从 `nodeId: string` 改为 `nodeIds: string[]`
- [x] A6 前端 Canvas 右键菜单：多选状态下显示"重试 N 个节点"/"重试 N 个节点及下游"，无可用 cycle 时置灰 + tooltip
- [x] A7 前端右键逻辑：点在选中集合内→批量操作，点在集合外→清除多选切换单节点上下文
- [x] A8 前端触发后行为：清除选中态，用 `retry_nodes` 响应字段驱动节点"重试中"高亮
- [x] A9 更新 `apps/web-console/src/api/types.ts` 中 retry 相关类型定义

## 2. Checks

- [x] C1 验证多节点 single mode 重试按拓扑序执行
  - Covers: A1
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "retry" -v`
  - Expect: 选中节点内部按拓扑序执行，内部节点间传播新结果，外部输入使用 prefilled

- [x] C2 验证多节点 cascade mode 重试取并集
  - Covers: A1
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "retry" -v`
  - Expect: retry_nodes = ∪ downstream(node_i)，所有下游节点被重新执行

- [x] C3 验证 cycle_id 可选化默认取最近非 running run
  - Covers: A2
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_per_dag.py -k "retry" -v`
  - Expect: 不传 cycle_id 时使用最近一次已结束 run 的数据

- [x] C4 验证 API 参数变更和响应结构
  - Covers: A3
  - Command: `curl -X POST http://localhost:8000/api/pipeline/dag/default/retry -H 'Content-Type: application/json' -d '{"node_ids": ["node-1"], "mode": "single"}'`
  - Expect: 响应包含 `cycle_id`, `retry_of`, `node_ids`, `mode`, `retry_nodes` 字段

- [x] C5 验证 prefilled 数据缺失时返回 400
  - Covers: A4
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_per_dag.py -k "retry" -v`
  - Expect: 上游节点无可用 output 时返回 400 错误，包含缺失节点信息

- [x] C6 验证前端 mutation 参数变更
  - Covers: A5, A9
  - Command: `cd apps/web-console && npx tsc --noEmit`
  - Expect: TypeScript 编译无错误

- [x] C7 验证前端多选右键菜单行为
  - Covers: A6, A7, A8
  - Evidence: 浏览器手动测试
  - Expect: 多选后右键显示批量重试菜单项，无 cycle 时置灰带 tooltip，触发后清除选中态并高亮 retry_nodes
