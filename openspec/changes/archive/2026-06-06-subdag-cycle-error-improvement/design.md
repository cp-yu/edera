## Context

当前 Sub DAG 循环检测在 `packages/core/src/edera_core/dag/loader.py` 的 `validate_sub_dag_nesting` 函数中实现，使用 DFS 遍历检测引用环。检测到循环时抛出 `DagError(f"sub DAG cycle: {' -> '.join(chain)}")`，仅包含 DAG 名称路径。

错误消息通过 `graph_service.py::SaveDag` 的 `except DagError as exc: await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))` 传递到前端，前端使用 `window.alert(error.message)` 原样显示。

用户看到的消息如 "sub DAG cycle: demo -> demo"，无法知道具体是哪个节点实例导致了循环。

## Goals / Non-Goals

**Goals:**
- 增强错误消息，包含触发循环的具体节点实例 ID
- 提供清晰的循环路径可视化（DAG 名称 + 节点实例）
- 给出具体的修复建议（哪些节点可以移除或修改）
- 保持 Web 和 CLI 统一的错误消息格式
- 保持最小改动：仅修改后端检测逻辑和错误消息格式，前端无需变更

**Non-Goals:**
- 前端 UI 改进（如自定义 Dialog 替代 alert）
- 错误消息国际化或本地化机制
- 实时前端循环预检测
- 性能优化（当前 DFS 性能已足够）

## Decisions

### 决策 1：使用 DagPathStep 数据类追踪路径

**选择：** 引入 `DagPathStep` 数据类，包含 `dag_name` 和 `via_node_id` 两个字段。

**理由：**
- 类型清晰，代码可读性好
- 易于扩展（未来可加入 `node_alias` 等字段）
- 比 tuple 嵌套或分离的双路径参数更易维护

**替代方案：**
- 方案 A：使用 `tuple[tuple[str, str | None], ...]` 嵌套结构 → 可读性差
- 方案 C：分离 `dag_path` 和 `node_path` 两个参数 → 需要同步维护，容易出错

### 决策 2：错误消息格式

**选择：** 多行详细格式，包含循环路径、问题说明和修复建议三部分。

示例：
```
无法保存 DAG 'demo'：检测到 Sub DAG 循环 (Sub DAG cycle detected)

循环路径：
  demo
    -> [节点 'sub-1'] -> demo

问题：Sub DAG 引用形成了循环。
修复建议：请移除或修改以下节点的引用：
  • demo 中的节点 'sub-1'
```

**理由：**
- 中英文混合（技术术语保留英文）符合用户期望
- 结构化清晰，用户可快速定位问题节点
- 修复建议具体可操作
- 无需区分 Web/CLI 格式，`window.alert` 和终端输出均可正确显示多行文本

**替代方案：**
- 简要版（"检测到循环，无法保存"）→ 信息不足
- 纯英文格式 → 用户体验不够友好

### 决策 3：错误消息生成位置

**选择：** 在 `dag/loader.py` 的 `_visit_sub_dag` 函数内生成完整错误消息，新增 `_format_cycle_error` 辅助函数。

**理由：**
- 检测逻辑和错误消息格式化内聚，职责清晰
- `graph_service.py` 和 `dag/runner.py` 保持现有的 `str(exc)` 调用，无需改动
- 单一错误消息生成点，易于维护和测试

**替代方案：**
- 在 `graph_service.py` 捕获 DagError 后格式化 → 分散了格式化逻辑，不利于运行时复用

### 决策 4：同步更新运行时错误消息

**选择：** 同步更新 `dag/runner.py` 的运行时循环检测错误消息格式，保持一致性。

**理由：**
- 用户体验一致：保存时和运行时看到相同格式的错误
- 代码复用：可以使用同一个 `_format_cycle_error` 函数

## Risks / Trade-offs

### 风险 1：错误消息过长

**风险：** 对于深层循环（如 A → B → C → D → E → A），错误消息可能较长，`window.alert` 可能需要滚动。

**缓解措施：**
- 用户已明确表示可接受
- 未来可通过前端 UI 改进（自定义 Dialog）进一步优化，但不在本次范围内

### 风险 2：测试断言更新

**风险：** 现有测试 `test_save_sub_dag_cycle_rejected` 断言需要更新，可能影响 CI。

**缓解措施：**
- 测试更新是必需步骤，已纳入任务清单
- 测试更新后可提供更强的消息格式保障

### Trade-off：英文技术术语 vs 全中文

**选择：** 使用中英混合（"检测到 Sub DAG 循环 (Sub DAG cycle detected)"）

**权衡：**
- 优点：保留技术术语的精确性，便于用户搜索文档和日志
- 缺点：可能稍显冗余
- 结论：技术用户友好性优先

### Trade-off：实现复杂度 vs 信息完整度

**选择：** 追踪节点实例 ID，增加路径数据结构复杂度

**权衡：**
- 优点：提供完整的问题定位信息，显著改善用户体验
- 缺点：需要修改 `_visit_sub_dag` 函数签名和递归调用
- 结论：用户体验改进价值远大于实现成本
