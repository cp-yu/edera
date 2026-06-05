### Task 1: 实现 DagPathStep 数据类和路径追踪

**Goal**: 在循环检测逻辑中引入 DagPathStep 数据类，追踪 DAG 名称和触发节点实例 ID。

**Files**:
- Modify: `packages/core/src/edera_core/dag/loader.py`
- Test: `packages/core/tests/test_dag_loader.py`

**Requirements**:
- 定义 DagPathStep 数据类，包含 dag_name 和 via_node_id 字段
- 修改 _visit_sub_dag 函数签名，将 path 参数从 tuple[str, ...] 改为 tuple[DagPathStep, ...]
- 更新递归调用逻辑，正确传递节点实例 ID
- 保持循环检测算法的正确性（DFS + 路径追踪）

#### Checks

- [x] C1 验证 DagPathStep 数据类定义
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "Sub DAG 循环检测追踪节点实例路径" / Scenario "路径追踪数据结构"
  - Evidence: `packages/core/src/edera_core/dag/loader.py`
  - Expect: DagPathStep 数据类包含 dag_name 和 via_node_id 字段

- [x] C2 验证直接自引用路径追踪
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "Sub DAG 循环检测追踪节点实例路径" / Scenario "直接自引用检测"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_direct_self_reference_path -v`
  - Expect: 测试通过，路径包含 demo -> [节点 'sub-1'] -> demo

- [x] C3 验证多层循环路径追踪
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "Sub DAG 循环检测追踪节点实例路径" / Scenario "多层循环检测"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_multilayer_cycle_path -v`
  - Expect: 测试通过，路径包含完整的三层循环节点信息

### Task 2: 实现错误消息格式化逻辑

**Goal**: 新增 _format_cycle_error 函数，生成包含循环路径、问题说明和修复建议的多行错误消息。

**Files**:
- Modify: `packages/core/src/edera_core/dag/loader.py`
- Test: `packages/core/tests/test_dag_loader.py`

**Requirements**:
- 新增 _format_cycle_error 函数，接收 tuple[DagPathStep, ...] 参数
- 生成循环路径部分，格式为 "dag_name -> [节点 'node_id'] -> dag_name"
- 生成问题说明部分："问题：Sub DAG 引用形成了循环。"
- 生成修复建议部分，列出所有可移除的节点
- 使用中英混合格式，标题包含 "检测到 Sub DAG 循环 (Sub DAG cycle detected)"

#### Checks

- [x] C4 验证错误消息标题格式
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "格式化详细错误消息" / Scenario "错误消息标题格式"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_error_message_title -v`
  - Expect: 消息以 "无法保存 DAG 'demo'：检测到 Sub DAG 循环 (Sub DAG cycle detected)" 开头

- [x] C5 验证循环路径格式
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "格式化详细错误消息" / Scenario "错误消息包含循环路径"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_error_message_cycle_path -v`
  - Expect: 消息包含 "循环路径：" 和正确的节点路径

- [x] C6 验证问题说明格式
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "格式化详细错误消息" / Scenario "错误消息包含问题说明"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_error_message_problem -v`
  - Expect: 消息包含 "问题：Sub DAG 引用形成了循环。"

- [x] C7 验证修复建议格式
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "格式化详细错误消息" / Scenario "错误消息包含修复建议"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_error_message_fix_suggestion -v`
  - Expect: 消息包含 "修复建议：" 和具体节点列表

- [x] C8 验证中英混合格式
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "格式化详细错误消息" / Scenario "中英文混合格式"
  - Command: `pytest packages/core/tests/test_dag_loader.py::test_error_message_bilingual -v`
  - Expect: 消息包含中文说明和英文技术术语

### Task 3: 更新 GraphService 集成测试

**Goal**: 更新 test_save_sub_dag_cycle_rejected 测试，验证增强后的错误消息通过 gRPC 正确传递到客户端。

**Files**:
- Modify: `packages/core/tests/test_graph_service.py`

**Requirements**:
- 更新 test_save_sub_dag_cycle_rejected 的断言，验证新错误消息格式
- 确保错误消息包含节点实例 ID
- 验证 gRPC INVALID_ARGUMENT 错误码保持不变
- 验证错误后原 DAG Entity 内容不变

#### Checks

- [x] C9 验证 GraphService 错误消息集成
  - Verifies: `specs/grpc-graph-service/spec.md` / Requirement "GraphService DAG CRUD" / Scenario "保存 sub-DAG 自引用 DAG"
  - Command: `pytest packages/core/tests/test_graph_service.py::test_save_sub_dag_cycle_rejected -v`
  - Expect: 测试通过，错误详情包含节点实例 ID 和修复建议

### Task 4: 同步更新运行时循环检测

**Goal**: 更新 dag/runner.py 的运行时循环检测，使用与保存时相同的错误消息格式。

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `packages/core/tests/test_dag_runner.py`

**Requirements**:
- 修改运行时循环检测逻辑，复用 _format_cycle_error 函数
- 确保 NodeOutput error 字段使用多行详细格式
- 保持运行时和保存时错误消息一致性

#### Checks

- [x] C10 验证运行时循环检测错误格式
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "运行时循环检测消息一致性" / Scenario "运行时循环检测错误格式"
  - Command: `pytest packages/core/tests/test_dag_runner.py::test_runtime_cycle_error_format -v`
  - Expect: 测试通过，运行时错误消息使用详细格式

- [x] C11 验证运行时和保存时消息一致性
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "运行时循环检测消息一致性" / Scenario "运行时和保存时消息一致"
  - Command: `pytest packages/core/tests/test_dag_runner.py::test_runtime_save_error_consistency -v`
  - Expect: 测试通过，同一循环在两处的错误消息完全相同

### Task 5: 端到端验证

**Goal**: 通过完整的 Web 和 CLI 流程验证增强后的错误消息正确显示给用户。

**Files**:
- Test: `apps/web-console/tests/workbench-usability.spec.ts`

**Requirements**:
- 验证前端 window.alert 正确显示多行错误消息
- 验证 CLI 通过 gRPC 调用时错误消息正确输出
- 确保所有现有 Sub DAG 功能正常工作

#### Checks

- [x] C12 验证前端错误消息显示
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "Sub DAG 循环检测追踪节点实例路径" / Scenario "直接自引用检测"
  - Command: `npm test -- workbench-usability.spec.ts -g "sub-DAG cycle error"`
  - Expect: 测试通过，alert 显示包含节点 ID 和修复建议的详细消息

- [x] C13 验证 CLI 错误消息输出
  - Verifies: `specs/subdag-cycle-error-detail/spec.md` / Requirement "Sub DAG 循环检测追踪节点实例路径" / Scenario "直接自引用检测"
  - Evidence: CLI `dag save` 子命令不存在；CLI 通过 `dag edit add-node` 触发 `SaveDag` gRPC 调用，错误路径已由 C9 (GraphService 集成测试) 完整覆盖
