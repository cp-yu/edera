## MODIFIED Requirements

### Requirement: Runtime status display
系统 SHALL 展示指定 DAG 的当前运行状态和最近运行记录。前端 SHALL 在 DAG 运行期间以固定间隔（2s）轮询节点运行状态，运行结束后停止轮询。

#### Scenario: View per-DAG pipeline status
- **WHEN** 用户查询指定 DAG 的管道状态
- **THEN** 系统 SHALL 返回调度器状态、当前 cycle_id 和最近运行记录

#### Scenario: Poll node status during active run
- **WHEN** DAG 处于运行中状态
- **THEN** 前端 SHALL 每 2 秒刷新一次 `GET /api/graph/runtime-status`，画布节点实时反映最新状态

#### Scenario: Stop polling after run completes
- **WHEN** DAG 运行结束（`current_cycle_id` 变为 null）
- **THEN** 前端 SHALL 停止对 `GET /api/graph/runtime-status` 的轮询
