# edge-optional Specification

## Purpose
此规约记录变更 core-architecture-overhaul 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Edge Optional 属性
Edge model SHALL 支持 `optional` 布尔字段（默认 false）。当边标记为 optional 时，上游节点失败 SHALL NOT 阻塞下游节点执行。

#### Scenario: Optional 边上游失败不阻塞
- **WHEN** 边 A→B 标记为 `optional: true`，且节点 A 执行失败
- **THEN** 节点 B SHALL 仍然执行，A 的输出视为缺失

#### Scenario: Required 边上游失败阻塞
- **WHEN** 边 A→B 标记为 `optional: false`（或未设置），且节点 A 执行失败
- **THEN** 节点 B SHALL 被阻塞，标记为失败

### Requirement: 节点级 Optional 语法糖
NodeConfig SHALL 支持 `optional` 布尔字段（默认 false）。当节点标记为 optional 时，等价于该节点的所有出边均标记为 optional。

#### Scenario: 节点 optional 展开为出边 optional
- **WHEN** 节点 A 配置 `optional: true`，且有出边 A→B 和 A→C
- **THEN** 系统 SHALL 将两条边均视为 `optional: true`

### Requirement: Fan-in Barrier Optional 判定
Executor 的 fan-in barrier 逻辑 SHALL 区分 optional 和 required 边。当所有 required 边的上游完成（或所有入边均为 optional）时，下游节点 SHALL 开始执行。

#### Scenario: Required 边全部完成触发执行
- **WHEN** 节点 C 有入边 A→C（required）和 B→C（optional），且 A 完成
- **THEN** 节点 C SHALL 开始执行，不等待 B

#### Scenario: 所有入边均 optional 时立即执行
- **WHEN** 节点 C 的所有入边均为 optional，且至少一个上游完成
- **THEN** 节点 C SHALL 开始执行

#### Scenario: Required 边上游失败阻塞下游
- **WHEN** 节点 C 有入边 A→C（required），且 A 失败
- **THEN** 节点 C SHALL 被标记为失败，不执行

### Requirement: Optional 边数据缺失处理
当 optional 边的上游失败时，下游节点接收的业务 `payload` SHALL 排除该失败上游，MUST NOT 使用 `null` 或 `None` 作为 payload 占位。系统 SHALL 在 runtime facts 和当前节点输入上下文中记录该 optional 上游失败。

#### Scenario: Optional 边数据缺失标记
- **WHEN** 节点 C 有入边 A→C（optional）和 B→C（required），A 失败，B 成功
- **THEN** 节点 C 接收的 `payload` SHALL 仅包含 B 的输出，并且 A→C 的失败 SHALL 记录在 `edge_inputs` 和当前节点输入上下文中

#### Scenario: Optional 边不得污染 list 输入
- **WHEN** 节点 C 的 input type 为 `list[RawItem]`，且 optional 上游 A 失败
- **THEN** 节点 C 的 `payload` MUST NOT 包含 `None`

