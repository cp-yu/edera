### Task 1: 新增 InputMapping EntityType

**Goal**: 创建 `input_mapping` 核心 Entity Type 和数据库表

**Files**:
- Create: `alembic/versions/xxxx_add_input_mapping_entity_type.py`
- Modify: `packages/core/src/edera_core/config/schema.py`
- Test: `packages/core/tests/test_input_mapping_entity.py`

**Requirements**:
- 定义 `input_mapping` EntityType，包含 `name`、`shared`、`nodes`、`append_nodes` 字段
- 创建 `entity_input_mapping` 数据库表
- 标记为 `system_protected: true`
- 支持 CRUD 操作

#### Checks

- [x] C1 验证 InputMapping entity 创建
  - Verifies: `specs/input-mapping-entity/spec.md` / Requirement "InputMapping EntityType 定义" / Scenario "创建 InputMapping entity"
  - Command: `pytest packages/core/tests/test_input_mapping_entity.py::test_create_input_mapping_entity`
  - Expect: 测试通过，entity 成功存储到数据库

- [x] C2 验证系统保护
  - Verifies: `specs/input-mapping-entity/spec.md` / Requirement "InputMapping entity 的系统保护" / Scenario "用户尝试删除 InputMapping EntityType"
  - Command: `pytest packages/core/tests/test_input_mapping_entity.py::test_delete_protected_type`
  - Expect: 测试通过，返回 403 错误

### Task 2: 实现节点输入三步解析逻辑

**Goal**: 在 DagRunner 中实现节点输入的三步解析（base → 临时输入 → 模式）

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `packages/core/tests/test_node_input_resolution.py`

**Requirements**:
- 新增 `_get_node_input()` 方法实现三步逻辑
- 新增 `_is_source_node()` 辅助方法
- 新增 `_merge()` 浅合并方法
- 支持 `sourceSharedInputs`、`nodeInputs`、`appendNodes` 参数

#### Checks

- [x] C3 验证 source 节点无临时输入使用默认配置
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "节点输入三步解析逻辑" / Scenario "Source 节点无临时输入使用默认配置"
  - Command: `pytest packages/core/tests/test_node_input_resolution.py::test_source_no_temp_input`
  - Expect: 测试通过，节点输入为 `node.config.default_entity`

- [x] C4 验证 nodeInputs 覆盖模式
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "节点输入三步解析逻辑" / Scenario "nodeInputs 覆盖模式"
  - Command: `pytest packages/core/tests/test_node_input_resolution.py::test_node_inputs_replace`
  - Expect: 测试通过，节点输入完全替换

- [x] C5 验证 nodeInputs 追加模式
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "节点输入三步解析逻辑" / Scenario "nodeInputs 追加模式"
  - Command: `pytest packages/core/tests/test_node_input_resolution.py::test_node_inputs_append`
  - Expect: 测试通过，节点输入为 merge 结果

- [x] C6 验证 sourceSharedInputs 仅对 source 生效
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "节点输入三步解析逻辑" / Scenario "sourceSharedInputs 仅对 source 节点生效"
  - Command: `pytest packages/core/tests/test_node_input_resolution.py::test_source_shared_inputs`
  - Expect: 测试通过，source 节点使用 sourceSharedInputs

- [x] C7 验证浅合并语义
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "浅合并语义" / Scenario "Dict 浅合并"
  - Command: `pytest packages/core/tests/test_node_input_resolution.py::test_shallow_merge`
  - Expect: 测试通过，dict 浅合并正确

### Task 3: 移除旧的 input_binding 机制

**Goal**: 移除 `DAG.inputs`、`input_binding` 相关代码和逻辑

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `packages/core/tests/test_deprecated_fields.py`

**Requirements**:
- 从 schema 中移除 `inputs` 和 `input_binding` 字段
- 移除 `_source_payload()` 和 `_input_binding()` 方法
- 添加检测逻辑，给出清晰错误提示

#### Checks

- [x] C8 验证 input_binding 错误提示
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "错误提示" / Scenario "检测到 input_binding"
  - Command: `pytest packages/core/tests/test_deprecated_fields.py::test_input_binding_error`
  - Expect: 测试通过，抛出清晰的迁移建议错误

- [x] C9 验证 DAG.inputs 错误提示
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "错误提示" / Scenario "检测到 DAG.inputs"
  - Command: `pytest packages/core/tests/test_deprecated_fields.py::test_dag_inputs_error`
  - Expect: 测试通过，抛出清晰的迁移建议错误

### Task 4: Sub-DAG input_mapping 支持 entity 引用

**Goal**: 修改 Sub-DAG 的 `input_mapping` 支持 dict 或 entity 引用

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Modify: `packages/core/src/edera_core/config/schema.py`
- Test: `packages/core/tests/test_subdag_input_mapping.py`

**Requirements**:
- `DagNodeConfig.input_mapping` 类型改为 `dict[str, str] | str`
- 新增 `_resolve_input_mapping()` 方法解析 entity 引用
- 从 InputMapping entity 读取 `shared`、`nodes`、`append_nodes`

#### Checks

- [x] C10 验证 input_mapping 为 dict 类型
  - Verifies: `specs/sub-dag-execution/spec.md` / Requirement "Dag 节点类型支持" / Scenario "input_mapping 为 dict 类型"
  - Command: `pytest packages/core/tests/test_subdag_input_mapping.py::test_input_mapping_dict`
  - Expect: 测试通过，使用 dict 映射到 sourceSharedInputs

- [x] C11 验证 input_mapping 为 entity 引用
  - Verifies: `specs/sub-dag-execution/spec.md` / Requirement "Dag 节点类型支持" / Scenario "input_mapping 为 entity 引用"
  - Command: `pytest packages/core/tests/test_subdag_input_mapping.py::test_input_mapping_entity`
  - Expect: 测试通过，从 entity 读取映射配置

- [x] C12 验证 InputMapping 解析和应用
  - Verifies: `specs/input-mapping-entity/spec.md` / Requirement "InputMapping 解析和应用" / Scenario "映射父节点输出到子 DAG 共享输入"
  - Command: `pytest packages/core/tests/test_subdag_input_mapping.py::test_mapping_application`
  - Expect: 测试通过，子 DAG 接收正确的输入参数

### Task 5: 更新 gRPC API

**Goal**: 修改 gRPC proto 定义和服务实现，增加临时输入参数

**Files**:
- Modify: `packages/core/src/edera_core/proto/edera.proto`
- Modify: `packages/core/src/edera_core/grpc_services.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `packages/core/tests/test_grpc_dag_service.py`

**Requirements**:
- `DagRunRequest` 增加 `source_shared_inputs_json`、`node_inputs_json`、`append_nodes_json` 字段
- `RetryRequest` 增加相同字段
- `DagController` 方法支持临时输入参数

#### Checks

- [x] C13 验证 DAG run API 临时输入参数
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "DAG run API 临时输入参数" / Scenario "运行 DAG 时指定 sourceSharedInputs"
  - Command: `pytest packages/core/tests/test_grpc_dag_service.py::test_run_with_temp_inputs`
  - Expect: 测试通过，临时输入参数正确传递

- [x] C14 验证 Retry API 临时输入参数
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "Retry API 临时输入参数" / Scenario "Retry 时覆盖节点输入"
  - Command: `pytest packages/core/tests/test_grpc_dag_service.py::test_retry_with_temp_inputs`
  - Expect: 测试通过，Retry 时临时输入参数正确传递

### Task 6: Node trigger 支持追加模式

**Goal**: 修改 `run_node_trigger` 支持 `append` 参数

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `packages/core/tests/test_node_trigger_append.py`

**Requirements**:
- `run_node_trigger()` 增加 `append` 参数
- 当 `append=True` 时，将 node_id 加入 `appendNodes`

#### Checks

- [x] C15 验证 Node trigger 覆盖模式
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "Node trigger 支持追加模式" / Scenario "Node trigger 覆盖模式"
  - Command: `pytest packages/core/tests/test_node_trigger_append.py::test_trigger_replace`
  - Expect: 测试通过，节点输入完全替换

- [x] C16 验证 Node trigger 追加模式
  - Verifies: `specs/runtime-temporary-input/spec.md` / Requirement "Node trigger 支持追加模式" / Scenario "Node trigger 追加模式"
  - Command: `pytest packages/core/tests/test_node_trigger_append.py::test_trigger_append`
  - Expect: 测试通过，节点输入为 base + 追加参数

### Task 7: 更新 Web BFF API

**Goal**: 修改 edera-web BFF 的 HTTP API，增加临时输入参数

**Files**:
- Modify: `apps/edera-web/src/routes/dags.py`
- Test: `apps/edera-web/tests/test_dag_api.py`

**Requirements**:
- `POST /api/dags/{name}/run` 接受 `sourceSharedInputs`、`nodeInputs`、`appendNodes`
- `POST /api/dags/{name}/retry` 接受相同参数
- 通过 gRPC 传递给 edera-server

#### Checks

- [x] C17 验证 DAG run HTTP API
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "DAG run HTTP API" / Scenario "传递临时输入参数"
  - Command: `pytest apps/edera-web/tests/test_dag_api.py::test_run_with_temp_inputs`
  - Expect: 测试通过，HTTP API 接受并传递临时输入参数

- [x] C18 验证 Retry HTTP API
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "Retry HTTP API" / Scenario "Retry 时传递临时输入"
  - Command: `pytest apps/edera-web/tests/test_dag_api.py::test_retry_with_temp_inputs`
  - Expect: 测试通过，Retry API 接受并传递临时输入参数

### Task 8: Web Console 临时输入 UI

**Goal**: 在 Web Console 增加临时输入配置弹窗和交互

**Files**:
- Create: `apps/web-console/src/components/TemporaryInputDialog.tsx`
- Modify: `apps/web-console/src/features/workbench/components/BottomToolbar.tsx`
- Modify: `apps/web-console/src/features/workbench/components/Canvas.tsx`
- Modify: `apps/web-console/src/api/mutations.ts`

**Requirements**:
- 创建 `TemporaryInputDialog` 组件支持配置临时输入
- 运行按钮旁增加配置入口
- Retry 右键菜单增加配置入口
- 更新 API mutations 增加临时输入参数

#### Checks

- [x] C19 验证运行 DAG 时打开临时输入弹窗
  - Verifies: `specs/node-graph-dag-editor/spec.md` / Requirement "DAG 运行控制" / Scenario "运行 DAG 时打开临时输入弹窗"
  - Evidence: 手动测试 Web Console，点击配置图标
  - Expect: 弹窗打开，显示 sourceSharedInputs、nodeInputs、appendNodes 配置界面

- [x] C20 验证配置临时输入后运行
  - Verifies: `specs/node-graph-dag-editor/spec.md` / Requirement "DAG 运行控制" / Scenario "配置临时输入后运行"
  - Evidence: 手动测试 Web Console，配置临时输入后运行
  - Expect: DAG 运行，节点使用临时输入

- [x] C21 验证 Retry 时打开临时输入弹窗
  - Verifies: `specs/node-graph-dag-editor/spec.md` / Requirement "Retry 操作支持临时输入" / Scenario "Retry 时打开临时输入弹窗"
  - Evidence: 手动测试 Web Console，右键节点选择 Retry 并配置输入
  - Expect: 弹窗打开，显示临时输入配置界面

### Task 9: Entity 管理页面支持 InputMapping

**Goal**: 在 Web Console Entity 管理页面增加 InputMapping 类型支持

**Files**:
- Modify: `apps/web-console/src/features/entities/EntityManagementPage.tsx`

**Requirements**:
- Entity 类型列表增加 `input_mapping`
- 支持创建、编辑、查看、删除 InputMapping entities

#### Checks

- [x] C22 验证 Entity 管理页面列出 InputMapping
  - Verifies: `specs/input-mapping-entity/spec.md` / Requirement "Web Console 管理 InputMapping entity" / Scenario "Entity 管理页面列出 InputMapping"
  - Evidence: 手动测试 Web Console，访问 Entity 管理页面选择 input_mapping 类型
  - Expect: 页面显示所有 InputMapping entities

- [x] C23 验证创建 InputMapping entity
  - Verifies: `specs/input-mapping-entity/spec.md` / Requirement "Web Console 管理 InputMapping entity" / Scenario "创建 InputMapping entity"
  - Evidence: 手动测试 Web Console，创建新的 InputMapping entity
  - Expect: Entity 创建成功，列表刷新

### Task 10: 迁移现有配置

**Goal**: 调用 subagent 迁移现有 DAG 和 Node 配置

**Files**:
- Modify: 所有现有 DAG 和 Node 配置文件

**Requirements**:
- 删除所有 `DAG.inputs` 字段
- 将所有 `input_binding` 移到 `config.default_entity`

#### Checks

- [x] C24 验证配置迁移完成
  - Verifies: `specs/dag-input-parameters/spec.md` / Requirement "运行时参数传递" / Scenario "CLI 传递 sourceSharedInputs"
  - Command: `grep -r "input_binding\|inputs:" packages/ --include="*.yaml" --include="*.py"`
  - Expect: 没有匹配结果，所有旧字段已移除
