---
capabilities:
  - cap.core.subdag-cycle-error-detail
---
# subdag-cycle-error-detail Specification

## Purpose
定义 Sub DAG 循环检测的增强错误消息格式，包含节点级路径追踪和具体修复建议。

## MODIFIED Requirements

### Requirement: Sub DAG 循环检测追踪节点实例路径

系统 SHALL 在检测到 Sub DAG 循环时追踪完整的 DAG 路径和触发循环的节点实例 ID，并在错误消息中包含这些信息。

#### Scenario: 直接自引用检测

- **WHEN** 用户保存 DAG 'demo'，其中包含一个 `type: "dag", dag_ref: "demo"` 的节点实例 'sub-1'
- **THEN** 系统 SHALL 检测到循环并抛出 DagError，错误消息 MUST 包含：
  - 根 DAG 名称 'demo'
  - 触发循环的节点实例 ID 'sub-1'
  - 目标 DAG 名称 'demo'

#### Scenario: 多层循环检测

- **WHEN** DAG 'pipeline-a' 中节点 'step-b' 引用 'pipeline-b'，'pipeline-b' 中节点 'step-c' 引用 'pipeline-c'，'pipeline-c' 中节点 'back-to-a' 引用 'pipeline-a'
- **THEN** 系统 SHALL 检测到循环并抛出 DagError，错误消息 MUST 包含完整路径：
  - pipeline-a -> [节点 'step-b'] -> pipeline-b
  - pipeline-b -> [节点 'step-c'] -> pipeline-c
  - pipeline-c -> [节点 'back-to-a'] -> pipeline-a

#### Scenario: 路径追踪数据结构

- **WHEN** 循环检测函数遍历 Sub DAG 引用
- **THEN** 系统 SHALL 使用 DagPathStep 数据类记录路径，每个步骤包含：
  - `dag_name`: DAG 名称
  - `via_node_id`: 触发引用的节点实例 ID（根 DAG 为 None）

### Requirement: 格式化详细错误消息

系统 SHALL 生成多行格式化错误消息，包含循环路径、问题说明和修复建议三部分。

#### Scenario: 错误消息包含循环路径

- **WHEN** 检测到 Sub DAG 循环
- **THEN** 错误消息 MUST 包含 "循环路径：" 部分，格式为：
  ```
  循环路径：
    <root-dag>
      -> [节点 '<node-id>'] -> <next-dag>
      -> [节点 '<node-id>'] -> <final-dag>
  ```

#### Scenario: 错误消息包含问题说明

- **WHEN** 检测到 Sub DAG 循环
- **THEN** 错误消息 MUST 包含 "问题：Sub DAG 引用形成了循环。" 说明

#### Scenario: 错误消息包含修复建议

- **WHEN** 检测到 Sub DAG 循环
- **THEN** 错误消息 MUST 包含 "修复建议：" 部分，列出所有可以移除或修改的节点，格式为：
  ```
  修复建议：请移除或修改以下任一节点的引用：
    • <dag-name> 中的节点 '<node-id>'
    • <dag-name> 中的节点 '<node-id>'
  ```

#### Scenario: 中英文混合格式

- **WHEN** 生成错误消息
- **THEN** 系统 SHALL 使用中英混合格式，标题和说明使用中文，技术术语（如 "Sub DAG cycle detected"）保留英文

#### Scenario: 错误消息标题格式

- **WHEN** 检测到 Sub DAG 循环
- **THEN** 错误消息 MUST 以标题开头，格式为：
  ```
  无法保存 DAG '<dag-name>'：检测到 Sub DAG 循环 (Sub DAG cycle detected)
  ```

### Requirement: 运行时循环检测消息一致性

系统 SHALL 在运行时 Sub DAG 循环检测中使用与保存时相同的错误消息格式。

#### Scenario: 运行时循环检测错误格式

- **WHEN** DAG 运行时检测到 Sub DAG 循环
- **THEN** 返回的 NodeOutput error 字段 MUST 使用与保存时相同的多行详细格式

#### Scenario: 运行时和保存时消息一致

- **WHEN** 同一个 Sub DAG 循环在保存时和运行时均被检测到
- **THEN** 两次错误消息的循环路径和修复建议 MUST 完全相同
