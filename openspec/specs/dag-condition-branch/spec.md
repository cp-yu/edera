---
capabilities:
  - cap.dag-condition-branch
---
# dag-condition-branch Specification

## Purpose
定义 Edge 条件表达式、默认 Condition Evaluator、Condition Evaluator 可替换、条件死路径检测。
## Requirements
### Requirement: Edge 条件表达式

系统 SHALL 支持在 DAG edge 上定义条件表达式。当条件求值为 true 时，数据 MUST 路由到该边的目标节点。

#### Scenario: 条件为 true 时路由数据

- **WHEN** edge 定义 `condition: "output.sentiment == 'negative'"`，且上游节点输出 `{sentiment: "negative"}`
- **THEN** 系统将数据路由到该边的目标节点

#### Scenario: 条件为 false 时不路由

- **WHEN** edge 定义 `condition: "output.sentiment == 'negative'"`，且上游节点输出 `{sentiment: "positive"}`
- **THEN** 系统不将数据路由到该边的目标节点

#### Scenario: 无条件边始终路由

- **WHEN** edge 未定义 `condition` 字段
- **THEN** 系统始终将数据路由到该边的目标节点

#### Scenario: 多条件都满足时并行分支

- **WHEN** 同一节点有两条出边，条件分别为 `"output.score > 0.5"` 和 `"output.score > 0.3"`，且输出 `{score: 0.8}`
- **THEN** 系统将数据同时路由到两条边的目标节点（并行分支）

### Requirement: 默认 Condition Evaluator

系统 SHALL 提供默认的条件求值器，支持受限 DSL 语法。

#### Scenario: 基本比较运算

- **WHEN** 条件表达式为 `"output.confidence > 0.8"`，输出 `{confidence: 0.9}`
- **THEN** evaluator 求值为 true

#### Scenario: Entity 引用操作数

- **WHEN** 条件表达式为 `"output.price > entity:stock:00700.threshold"`，且 `stock:00700` Entity 的 `threshold` 字段值为 100，输出 `{price: 120}`
- **THEN** evaluator 解析 entity 引用，求值为 true

#### Scenario: 逻辑组合

- **WHEN** 条件表达式为 `"output.sentiment == 'negative' and output.confidence > 0.7"`
- **THEN** evaluator 正确求值 AND 逻辑组合

#### Scenario: in 运算符

- **WHEN** 条件表达式为 `"output.category in ['tech', 'finance']"`，输出 `{category: "tech"}`
- **THEN** evaluator 求值为 true

### Requirement: Condition Evaluator 可替换

系统 SHALL 支持用户注册自定义 condition evaluator handler 替换默认实现。自定义 evaluator MUST 放置在 `config/evaluators/` 目录。

#### Scenario: 注册自定义 evaluator

- **WHEN** 用户在 `config/evaluators/custom.py` 中实现了 `evaluate(expression, context)` 函数
- **THEN** 系统加载该 evaluator 并用于条件求值

#### Scenario: 自定义 evaluator 加载失败

- **WHEN** 自定义 evaluator 文件存在语法错误
- **THEN** 系统回退到默认 evaluator 并记录 warning

### Requirement: 条件死路径检测

系统 SHALL 在 DAG 执行时检测条件死路径（所有条件边都不满足的情况），MUST 记录 warning 到 run metadata。

#### Scenario: 所有条件边都不满足

- **WHEN** 一个节点的所有出边都有条件，且所有条件都求值为 false
- **THEN** 系统记录 warning 到 run metadata，标记该路径为 dead path，不视为执行错误
