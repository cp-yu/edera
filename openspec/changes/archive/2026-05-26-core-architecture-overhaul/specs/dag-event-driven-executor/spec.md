## ADDED Requirements

### Requirement: Fan-in barrier 增加 edge optional 判定
系统 SHALL 在 fan-in barrier 模式中区分 optional 和 required 边。当所有 required 边的上游完成（或所有入边均为 optional）时，下游节点 SHALL 开始执行。Optional 边的上游失败 SHALL NOT 阻塞下游。

#### Scenario: Required 边全部完成触发执行
- **WHEN** node-C 有入边 A→C（required）和 B→C（optional），且 A 完成
- **THEN** dispatcher SHALL 启动 node-C，不等待 B

#### Scenario: Optional 边上游失败不阻塞
- **WHEN** node-C 有入边 A→C（optional）和 B→C（required），A 失败，B 成功
- **THEN** dispatcher SHALL 启动 node-C，A 的输出标记为 null

#### Scenario: 所有 required 边上游失败阻塞下游
- **WHEN** node-C 有入边 A→C（required），且 A 失败
- **THEN** node-C SHALL 被标记为失败，不执行
