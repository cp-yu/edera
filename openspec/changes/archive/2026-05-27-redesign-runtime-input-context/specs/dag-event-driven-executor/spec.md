## MODIFIED Requirements

### Requirement: 错误路径隔离
系统 SHALL 在节点失败时仅阻断该节点的 required 下游路径，MUST NOT 影响独立路径上的节点执行。Optional 边的上游失败 SHALL NOT 阻塞下游，且 MUST NOT 向下游 payload 注入失败占位。

#### Scenario: 失败节点阻断下游
- **WHEN** node-C 执行失败且 node-D 仅通过 required 边依赖 node-C
- **THEN** node-D MUST NOT 被启动，且 node-D 的 `node_runs` SHALL 记录 `status=failed`、`failure_kind=upstream_failed`

#### Scenario: 独立路径不受影响
- **WHEN** node-C 执行失败，但 node-E 位于独立路径（不依赖 node-C）
- **THEN** node-E MUST 正常执行

#### Scenario: Optional 节点失败视为入边失败事实
- **WHEN** 标记为 `optional: true` 的节点执行失败
- **THEN** dispatcher MUST 将其 optional 出边记录为 failed edge input facts，并 SHALL 正常评估下游节点，不得向下游 payload 注入 `None`

### Requirement: Fan-in barrier 增加 edge optional 判定
系统 SHALL 在 fan-in barrier 模式中区分 optional 和 required 边。当所有 required 边的上游完成（或所有入边均为 optional）时，下游节点 SHALL 开始执行。Optional 边的上游失败 SHALL NOT 阻塞下游，并且 SHALL 通过 runtime facts/context 记录。

#### Scenario: Required 边全部完成触发执行
- **WHEN** node-C 有入边 A→C（required）和 B→C（optional），且 A 完成
- **THEN** dispatcher SHALL 在调度 node-C 前写入 A→C 和 B→C 的 edge input facts，并启动 node-C

#### Scenario: Optional 边上游失败不阻塞
- **WHEN** node-C 有入边 A→C（optional）和 B→C（required），A 失败，B 成功
- **THEN** dispatcher SHALL 启动 node-C，node-C 的 payload SHALL 只包含 B 的输出，且 A→C SHALL 记录为 failed edge input

#### Scenario: 所有 required 边上游失败阻塞下游
- **WHEN** node-C 有入边 A→C（required），且 A 失败
- **THEN** node-C SHALL 被标记为 `status=failed`、`failure_kind=upstream_failed`，不执行，并写入 node-C 的所有直接入边 edge input facts
