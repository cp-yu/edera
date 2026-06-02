## ADDED Requirements

### Requirement: Dispatcher 支持 wait 节点挂起
中央 dispatcher SHALL 将 wait 节点作为常规 `asyncio.Task` 调度。当 wait 节点 Task 因等待外部输入而长时间不返回时，dispatcher MUST 通过 `asyncio.wait(FIRST_COMPLETED)` 继续处理其它已完成 Task，不得因 wait 节点挂起而阻塞主循环或独立路径。

#### Scenario: wait 节点挂起不阻塞主循环
- **WHEN** wait 节点 `gate` 的 Task 处于挂起（`waiting`）状态，其它节点 `worker` 正在执行
- **THEN** dispatcher SHALL 在 `worker` 完成时正常消费其完成事件并推进下游，不等待 `gate`

#### Scenario: wait 节点唤醒后正常汇入调度
- **WHEN** 挂起的 wait 节点 `gate` 被唤醒并返回 output
- **THEN** dispatcher SHALL 像处理普通节点完成一样消费 `gate` 完成事件并评估其下游就绪条件

#### Scenario: stop 时取消挂起的 wait 节点
- **WHEN** DAG run 收到 stop（`stop_event` 置位）且存在挂起的 wait 节点
- **THEN** 系统 SHALL 解除该 wait 节点挂起并按 run 既有 stop 路径终止
