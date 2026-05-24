## Why

当前 DAG 运行是黑盒——无法观测节点内部状态和输出数据流，无法在节点失败后重试，无法优雅中断运行中的 DAG。同时执行模型（layer-by-layer）与期望的 event-driven 数据流语义不符，前端缺少环检测警告和新建 DAG 入口。

## What Changes

- **执行模型重写**：DagRunner 从 layer-loop 改为 event-driven dispatcher（asyncio.Queue），节点完成即触发下游，不再等待整层完成
- **Fan-in 语义明确化**：目标节点配置 `fan_in_mode: barrier | accumulate`，barrier 为默认；accumulate 模式下并行 sub-task 处理各上游结果，完成后合并发给下游
- **Soft/Hard Stop**：注入 `asyncio.Event` 实现 soft stop（等当前节点完成后停止），保留 `task.cancel()` 作为 hard stop；`POST /api/pipeline/dag/{name}/stop` 增加 `force` 参数
- **节点重试**：新增 `POST /api/pipeline/dag/{dag_name}/retry`，支持 `single`（单点调试）和 `cascade`（从该节点起重跑下游）两种 mode；生成新 cycle_id 并通过 `retry_of` 字段关联原始 run
- **能观性 — Inspector Runtime tab**：Inspector 面板新增 Runtime tab，展示节点当前运行状态和 output entities
- **能观性 — Edge 数据流查看**：点击 edge 时 Inspector 切换为 edge 详情模式，展示上游节点产出的 entities
- **能观性 — 历史页面**：独立 route `/history/dag/{dag_name}/nodes/{node_id}`，展示节点在所有历史 cycle 中的运行记录和 output entities
- **前端环检测**：`onConnect` 时 DFS 检测，有环则 toast 警告并拒绝创建边
- **新建 DAG**：DAG dropdown 增加 "+ 新建" 选项，dialog 输入名称，`POST /api/graph/dag` 创建空 DAG yaml
- **错误传播**：仅阻断失败节点的下游路径，不影响独立路径
- **Optional 节点**：失败视为完成（payload=None），dispatcher 无需特殊逻辑

## Capabilities

### New Capabilities
- `dag-event-driven-executor`: event-driven DAG 执行引擎，覆盖中央 dispatcher、asyncio.Queue 调度、fan-in barrier/accumulate 模式和错误路径隔离
- `dag-run-control`: DAG 运行控制能力，覆盖 soft stop（asyncio.Event）、hard stop（task.cancel）和节点重试（single/cascade mode）
- `dag-run-observability`: DAG 运行能观性，覆盖 Inspector Runtime tab、edge 数据流查看和节点历史页面
- `dag-creation`: DAG 创建能力，覆盖前端 dialog 交互和后端 API 创建空 DAG 配置文件
- `dag-cycle-detection-ui`: 前端环检测，覆盖 onConnect DFS 校验和 toast 警告

### Modified Capabilities
- `dag-runner`: 执行模型从 layer-loop 重写为 event-driven dispatcher，fan-in 语义变更为 barrier/accumulate
- `pipeline-control`: PipelineRun 表增加 `retry_of` 字段和 `retry` trigger 值，stop API 增加 `force` 参数

## Impact

- **核心层**：`packages/core/src/stockimformation_core/dag/runner.py` 整体重写；`pipeline.py` 适配新 runner 接口和 retry/stop 逻辑
- **数据层**：`PipelineRun` 表增加 `retry_of` 列；`NodeRun` 状态流转适配 event-driven 模型
- **API 层**：新增 `POST /api/pipeline/dag/{name}/retry`、`POST /api/graph/dag`；修改 `POST /api/pipeline/dag/{name}/stop` 接受 `force` 参数
- **前端**：Inspector 组件扩展（Runtime tab、edge 详情模式）；新增历史页面 route；Canvas `onConnect` 增加环检测；DAG dropdown 增加创建入口
- **测试**：现有 `test_dag_runner.py` 需要适配新执行模型
