## MODIFIED Requirements

### Requirement: Source/Sink 接口映射
子 DAG 的 source 节点 SHALL 作为外部输入接口，sink 节点 SHALL 作为外部输出接口。Dag 节点的上游输出 SHALL 经 `input_mapping` 映射到子 DAG 的 `sourceSharedInputs`，不 SHALL 作为入口 payload 直接传递给所有 source 节点。子 DAG 的 sink 节点输出 SHALL 作为 dag 节点的输出。

#### Scenario: 上游输出映射到子 DAG source
- **WHEN** dag 节点接收上游输出
- **THEN** 该输出 SHALL 通过 `input_mapping` 映射到子 DAG 的 `sourceSharedInputs`，由子 DAG source 节点接收

#### Scenario: 子 DAG sink 输出作为节点输出
- **WHEN** 子 DAG 的 sink 节点执行完成
- **THEN** 其输出 SHALL 作为 dag 节点的输出传递给下游
