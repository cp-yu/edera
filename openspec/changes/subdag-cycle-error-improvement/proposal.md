## Why

当用户在 Workbench 中添加 Sub DAG 节点导致循环引用时，后端检测到错误并拒绝保存，但当前错误消息仅显示循环路径（例如 "sub DAG cycle: demo -> demo"），缺乏具体的节点信息和修复建议。用户无法快速定位是哪个节点实例导致了循环，也不知道如何修复。此变更通过增强错误消息，提供完整的节点路径和具体的修复建议，显著改善用户体验。

## What Changes

- 后端循环检测逻辑增强：追踪 DAG 路径和节点实例路径，定位触发循环的具体节点
- 错误消息格式改进：生成多行详细消息，包含循环路径、问题说明和修复建议
- 测试用例更新：验证增强后的错误消息格式
- Spec 文档更新：明确错误消息的格式要求

## Capabilities

### New Capabilities
- `subdag-cycle-error-detail`: Sub DAG 循环检测错误消息增强，提供节点级路径追踪和修复建议

### Modified Capabilities
- `grpc-graph-service`: 更新 SaveDag 错误响应的详情描述，明确包含节点实例信息

## Impact

**后端影响：**
- `packages/core/src/edera_core/dag/loader.py`: 新增 DagPathStep 数据类，修改 `_visit_sub_dag` 和 `validate_sub_dag_nesting` 函数，新增错误消息格式化逻辑
- `packages/core/tests/test_graph_service.py`: 更新 `test_save_sub_dag_cycle_rejected` 测试断言

**前端影响：**
- `apps/web-console/src/api/mutations.ts`: 无代码变更，但 `window.alert` 显示的错误消息格式变为多行详细格式

**文档影响：**
- `openspec/specs/grpc-graph-service/spec.md`: 更新 Scenario "保存 sub-DAG 自引用 DAG" 的错误详情描述

**运行时影响：**
- `packages/core/src/edera_core/dag/runner.py`: 可选同步更新运行时循环检测的错误消息格式（保持一致性）

**CLI 影响：**
- CLI 工具通过 gRPC 调用 GraphService.SaveDag 时，错误输出格式变为多行详细消息
