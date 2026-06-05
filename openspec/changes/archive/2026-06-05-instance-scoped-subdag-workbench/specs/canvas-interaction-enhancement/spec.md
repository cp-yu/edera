## ADDED Requirements

### Requirement: Sub-DAG node context menu entry
Canvas 节点右键菜单 SHALL 对可解析目标 DAG 的 sub-DAG 节点显示“进入 Sub DAG”操作。该操作 MUST 使用被右键点击的节点实例作为父上下文。

#### Scenario: Show enter action for sub-DAG node
- **WHEN** 用户右键点击节点实例 `nodeX`
- **AND** `nodeX` 可解析出目标 DAG `common-subdag`
- **THEN** 节点右键菜单 SHALL 显示“进入 Sub DAG”

#### Scenario: Hide enter action for regular node
- **WHEN** 用户右键点击普通 function、agent 或 wait 节点
- **THEN** 节点右键菜单 MUST NOT 显示“进入 Sub DAG”

#### Scenario: Enter uses clicked instance
- **WHEN** DAG `dagA` 中两个节点实例都引用 `common-subdag`
- **AND** 用户右键点击实例 `nodeX` 并选择“进入 Sub DAG”
- **THEN** Workbench SHALL 使用 `nodeX` 作为父节点实例上下文
- **AND** MUST NOT 使用另一个引用相同 DAG 的节点实例上下文
