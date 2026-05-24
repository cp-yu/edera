## 1. Actions

- [x] A1 重写 DagRunner 为 event-driven dispatcher 架构（asyncio.Queue + 中央循环）
- [x] A2 实现 fan-in barrier 模式（等待所有上游完成后启动目标节点）
- [x] A3 实现 fan-in accumulate 模式（上游完成即 spawn sub-task，全部完成后 collect）
- [x] A4 实现错误路径隔离（失败节点仅阻断下游，不影响独立路径）
- [x] A5 实现 optional 节点失败视为完成（payload=None）
- [x] A6 注入 asyncio.Event 实现 soft stop（dispatcher 检查 event，不启动新节点）
- [x] A7 修改 PipelineController.stop_current 支持 soft/hard 两种模式
- [x] A8 修改 `POST /api/pipeline/dag/{name}/stop` 接受 `force` 参数
- [x] A9 PipelineRun 表增加 `retry_of` 列（nullable str），增加 `"retry"` trigger 值
- [x] A10 实现 retry 逻辑：从 DB 加载原 cycle 已成功节点 output，预填 dispatcher 状态，启动目标节点
- [x] A11 新增 `POST /api/pipeline/dag/{dag_name}/retry` endpoint（single/cascade mode）
- [x] A12 Inspector 增加 Runtime tab，展示节点 status/error 和 output entities
- [x] A13 Inspector 支持 edge 选中模式，展示上游节点 output entities
- [x] A14 扩展节点右键菜单（查看当前运行状态、查看历史、重试节点、重试节点及下游）
- [x] A15 扩展 edge 右键菜单（查看上游节点历史）
- [x] A16 新增历史页面 route `/history/dag/{dag_name}/nodes/{node_id}`
- [x] A17 前端 onConnect 环检测（DFS 从 target 出发检查是否能到达 source）
- [x] A18 新增 `POST /api/graph/dag` endpoint 创建空 DAG 配置文件
- [x] A19 DAG dropdown 增加 "+ 新建 DAG" 选项和创建 dialog
- [x] A20 适配现有 test_dag_runner.py 测试到新执行模型

## 2. Checks

- [x] C1 验证 event-driven dispatcher 基本调度
  - Covers: A1
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "test_parallel_sources" -x`
  - Expect: 无上游依赖的节点并发启动，节点完成后立即触发下游（不等同层）

- [x] C2 验证 fan-in barrier 模式
  - Covers: A2
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "barrier" -x`
  - Expect: 多上游节点全部完成后目标节点才启动，input 为所有上游 output 的 collect

- [x] C3 验证 fan-in accumulate 模式
  - Covers: A3
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "accumulate" -x`
  - Expect: 每个上游完成时 spawn sub-task，全部 sub-task 完成后 collect 结果发给下游

- [x] C4 验证错误路径隔离
  - Covers: A4
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "error_path_isolation" -x`
  - Expect: 失败节点的下游不启动，独立路径正常执行完成

- [x] C5 验证 optional 节点失败视为完成
  - Covers: A5
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "optional" -x`
  - Expect: optional 节点失败后下游正常触发，收到 payload=None

- [x] C6 验证 soft stop
  - Covers: A6, A7
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "soft_stop" -x`
  - Expect: soft stop 后不启动新节点，等当前节点完成后返回，run 标记为 cancelled

- [x] C7 验证 hard stop
  - Covers: A7
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "hard_stop" -x`
  - Expect: hard stop 立即 cancel task，CancelledError 终止 dispatcher

- [x] C8 验证 stop API force 参数
  - Covers: A8
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_web_api.py -k "stop" -x`
  - Expect: 无 body 或 force=false 触发 soft stop，force=true 触发 hard stop

- [x] C9 验证 PipelineRun retry_of 字段
  - Covers: A9
  - Command: `cd packages/core && python -m pytest tests/core/unit/test_storage.py -k "retry" -x`
  - Expect: retry run 记录包含 retry_of 指向原始 cycle_id，trigger 为 "retry"

- [x] C10 验证 retry 逻辑（single mode）
  - Covers: A10, A11
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "retry_single" -x`
  - Expect: 仅重新执行目标节点，上游 output 从 DB 加载，新 cycle_id 生成

- [x] C11 验证 retry 逻辑（cascade mode）
  - Covers: A10, A11
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -k "retry_cascade" -x`
  - Expect: 从目标节点开始重新执行所有下游，上游 output 从 DB 加载

- [x] C12 验证 Inspector Runtime tab
  - Covers: A12
  - Evidence: 浏览器中选中节点后 Inspector 展示 Runtime tab
  - Expect: Runtime tab 展示节点 status、started_at、ended_at、error 和 output entities 列表

- [x] C13 验证 Inspector edge 详情模式
  - Covers: A13
  - Evidence: 浏览器中点击 edge 后 Inspector 切换为 edge 详情
  - Expect: 展示上游节点在当前 cycle 中产出的 entities 列表和"查看历史"链接

- [x] C14 验证节点右键菜单扩展
  - Covers: A14
  - Evidence: 浏览器中右键节点
  - Expect: 菜单包含：查看当前运行状态、查看历史、重试节点、重试节点及下游、删除节点、断开所有连接

- [x] C15 验证 edge 右键菜单扩展
  - Covers: A15
  - Evidence: 浏览器中右键 edge
  - Expect: 菜单包含"查看上游节点历史"选项，点击后跳转到 `/history/dag/{name}/nodes/{upstream_id}`

- [x] C16 验证历史页面
  - Covers: A16
  - Evidence: 浏览器访问 `/history/dag/{dag_name}/nodes/{node_id}`
  - Expect: 展示该节点所有历史 NodeRun 记录列表，点击可展开查看 output entities

- [x] C17 验证前端环检测
  - Covers: A17
  - Evidence: 浏览器中尝试创建会形成环的连线
  - Expect: 连线被拒绝，显示 toast 警告

- [x] C18 验证 DAG 创建 API
  - Covers: A18
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_web_api.py -k "create_dag" -x`
  - Expect: POST /api/graph/dag 创建空 yaml 文件，重复名称返回 409，非法名称返回 400

- [x] C19 验证 DAG 创建前端入口
  - Covers: A19
  - Evidence: 浏览器中点击 DAG dropdown "+ 新建 DAG"
  - Expect: 弹出 dialog，输入名称确认后切换到新 DAG 空画布

- [x] C20 验证现有测试适配
  - Covers: A20
  - Command: `cd packages/core && python -m pytest tests/core/integration/test_dag_runner.py -x`
  - Expect: 所有现有测试通过（适配新执行模型后）
