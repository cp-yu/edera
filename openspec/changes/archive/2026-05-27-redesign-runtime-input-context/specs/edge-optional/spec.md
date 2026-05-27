## MODIFIED Requirements

### Requirement: Optional 边数据缺失处理
当 optional 边的上游失败时，下游节点接收的业务 `payload` SHALL 排除该失败上游，MUST NOT 使用 `null` 或 `None` 作为 payload 占位。系统 SHALL 在 runtime facts 和当前节点输入上下文中记录该 optional 上游失败。

#### Scenario: Optional 边数据缺失标记
- **WHEN** 节点 C 有入边 A→C（optional）和 B→C（required），A 失败，B 成功
- **THEN** 节点 C 接收的 `payload` SHALL 仅包含 B 的输出，并且 A→C 的失败 SHALL 记录在 `edge_inputs` 和当前节点输入上下文中

#### Scenario: Optional 边不得污染 list 输入
- **WHEN** 节点 C 的 input type 为 `list[RawItem]`，且 optional 上游 A 失败
- **THEN** 节点 C 的 `payload` MUST NOT 包含 `None`
