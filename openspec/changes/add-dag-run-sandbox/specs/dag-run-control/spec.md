---
capabilities:
  - cap.operations.dag-run-control
---

# dag-run-control Delta

## MODIFIED Requirements

### Requirement: Soft stop

系统 SHALL 支持 soft stop：通知运行停止调度新节点，等待所有当前正在执行的节点完成后终止 DAG 运行。当 run 以 os-sandbox 子进程执行时，soft stop MUST 通过向子进程发送停止信号实现，信号语义等价于主进程内的 `asyncio.Event` 通知。

#### Scenario: Soft stop 不中断当前节点

- **WHEN** 用户触发 soft stop 且有节点正在执行
- **THEN** 系统 MUST 等待当前正在执行的节点完成，MUST NOT 启动新节点，完成后将 run 标记为 `cancelled`

#### Scenario: Soft stop 无运行中节点

- **WHEN** 用户触发 soft stop 且 dispatcher 处于等待 queue 状态（无节点在执行）
- **THEN** 系统 MUST 立即终止 dispatcher 循环并返回当前结果

#### Scenario: 沙箱 run 的 soft stop

- **WHEN** 用户对 os-sandbox 子进程 run 触发 soft stop
- **THEN** 系统 MUST 经子进程停止通道通知其停止调度新节点，子进程 MUST 等待当前节点完成后退出

### Requirement: Hard stop

系统 SHALL 支持 hard stop：立即取消 DAG 运行，中断所有正在执行的节点。当 run 以 os-sandbox 子进程执行时，hard stop MUST 通过终止子进程实现，等价于主进程内的 `task.cancel()`。

#### Scenario: Hard stop 立即中断

- **WHEN** 用户触发 hard stop（`force: true`）
- **THEN** 系统 MUST 立即终止 DAG 运行，中断所有正在执行的节点，run 标记为 `cancelled`

#### Scenario: 沙箱 run 的 hard stop

- **WHEN** 用户对 os-sandbox 子进程 run 触发 hard stop（`force: true`）
- **THEN** 系统 MUST 终止沙箱子进程及其全部后代进程，run 标记为 `cancelled`
