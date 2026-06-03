---
capabilities:
  - cap.web.node-graph-dag-editor
---
# connection-type-validation Specification

## Purpose
定义 Role-based connection constraint、Function node type matching — hard block、LLM node type matching — soft warning、Type compatibility rules等能力。
## Requirements
### Requirement: Role-based connection constraint
系统 SHALL 根据节点 role 约束连线方向：source 节点不允许入边，sink 节点不允许出边。

#### Scenario: Prevent input to source node
- **WHEN** 用户尝试将连线拖入一个 `role: source` 的节点
- **THEN** 系统 SHALL 阻止连线建立，目标 handle 显示红色反馈

#### Scenario: Prevent output from sink node
- **WHEN** 用户尝试从一个 `role: sink` 的节点拖出连线
- **THEN** 系统 SHALL 阻止连线建立（sink 节点不渲染输出 handle）

#### Scenario: Processor allows both directions
- **WHEN** 用户对 `role: processor` 的节点建立入边或出边
- **THEN** 系统 SHALL 允许连线建立

### Requirement: Function node type matching — hard block
系统 SHALL 在连线到 Function 节点时执行严格类型匹配，不兼容时硬阻止连线。

#### Scenario: Compatible types allow connection
- **WHEN** 上游节点 `output_type` 为 `list[RawItem]`，目标 Function 节点 `input_type` 为 `list[RawItem]`
- **THEN** 系统 SHALL 允许连线，handle 显示绿色反馈

#### Scenario: Incompatible types block connection
- **WHEN** 上游节点 `output_type` 为 `list[AnalysisResult]`，目标 Function 节点 `input_type` 为 `list[RawItem]`
- **THEN** 系统 SHALL 阻止连线建立，handle 显示红色反馈

#### Scenario: Any type accepts all inputs
- **WHEN** 目标 Function 节点 `input_type` 为 `Any`
- **THEN** 系统 SHALL 允许任何上游类型连入

### Requirement: LLM node type matching — soft warning
系统 SHALL 在连线到 LLM 节点时允许任何类型连入，但类型不匹配时显示警告。

#### Scenario: Matching types — normal connection
- **WHEN** 上游 `output_type` 与目标 LLM 节点 `input_type` 匹配
- **THEN** 系统 SHALL 允许连线，无警告

#### Scenario: Mismatched types — warning connection
- **WHEN** 上游 `output_type` 与目标 LLM 节点 `input_type` 不匹配
- **THEN** 系统 SHALL 允许连线建立，但连线渲染为黄色/虚线样式表示类型警告

### Requirement: Type compatibility rules
系统 SHALL 使用简单层级规则判断类型兼容性。

#### Scenario: Any is universally compatible
- **WHEN** 任一侧类型为 `Any`
- **THEN** 系统 SHALL 判定为兼容

#### Scenario: Generic list matching
- **WHEN** 两侧类型均为 `list[X]` 格式
- **THEN** 系统 SHALL 比较泛型参数 X 是否精确相同

#### Scenario: Exact string match fallback
- **WHEN** 类型不属于 `Any` 或 `list[X]` 格式
- **THEN** 系统 SHALL 使用字符串精确比较判断兼容性

### Requirement: Real-time drag feedback
系统 SHALL 在拖拽连线过程中实时反馈目标 handle 的兼容性。

#### Scenario: Valid target feedback
- **WHEN** 用户拖拽连线经过一个兼容的目标 handle
- **THEN** 系统 SHALL 将该 handle 高亮为绿色

#### Scenario: Invalid target feedback
- **WHEN** 用户拖拽连线经过一个不兼容的目标 handle
- **THEN** 系统 SHALL 将该 handle 高亮为红色

#### Scenario: Drop on invalid target
- **WHEN** 用户在红色 handle 上松手
- **THEN** 系统 SHALL 取消连线操作，不建立边
