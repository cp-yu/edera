### Task 1: 拆分 cli.py 为 cli/ 子包

**Goal**: 将 1666 行的 `cli.py` 拆分为 `cli/` 子包，每个子命令独占模块，通过 registry 统一注册。

**Files**:
- Delete: `packages/core/src/edera_core/cli.py`
- Create: `packages/core/src/edera_core/cli/__init__.py`
- Create: `packages/core/src/edera_core/cli/_common.py`
- Create: `packages/core/src/edera_core/cli/entity.py`
- Create: `packages/core/src/edera_core/cli/relation.py`
- Create: `packages/core/src/edera_core/cli/entity_type.py`
- Create: `packages/core/src/edera_core/cli/node.py`
- Create: `packages/core/src/edera_core/cli/node_type.py`
- Create: `packages/core/src/edera_core/cli/skill.py`
- Create: `packages/core/src/edera_core/cli/dag.py`
- Create: `packages/core/src/edera_core/cli/event.py`
- Create: `packages/core/src/edera_core/cli/system.py`
- Create: `packages/core/src/edera_core/cli/client.py`
- Create: `packages/core/src/edera_core/cli/config.py`
- Create: `packages/core/src/edera_core/cli/query.py`
- Create: `packages/core/src/edera_core/cli/source.py`
- Create: `packages/core/src/edera_core/cli/handler.py`
- Create: `packages/core/src/edera_core/cli/extension.py`

**Requirements**:
- `cli/__init__.py` 暴露 `main()` 入口，通过 `COMMANDS` registry 动态注册子命令
- 每个子命令模块暴露 `add_parser(subparser)` 和 `async dispatch(args, client)` 两个入口
- `_dispatch()` 通过 `importlib.import_module` 动态加载对应模块
- 共享工具（格式化、分页、错误输出）放入 `_common.py`
- 入口点 `edera = "edera_core.cli:main"` 保持有效

#### Checks

- [ ] C1 验证 CLI 启动与子命令发现
  - Preserves: `openspec/specs/edera-cli/spec.md` / Requirement "edera CLI 提供完整控制面子命令集" / Scenario "列出所有子命令"
  - Command: `uv run edera --help`
  - Expect: 输出包含全部 15 个子命令（entity、relation、entity-type、node、node-type、skill、dag、event、system、client、config、query、source、handler、extension、handler-validate）

- [ ] C2 验证 entity 子命令行为不变
  - Preserves: `openspec/specs/edera-cli/spec.md` / Requirement "edera CLI 提供完整控制面子命令集" / Scenario "entity 子命令 list/get/create"
  - Command: `uv run edera entity list --type node --output json`
  - Expect: 返回合法 JSON，结构不变

- [ ] C3 验证 dag 子命令行为不变
  - Preserves: `openspec/specs/dag-run-control/spec.md` / Requirement "DAG 运行控制能力" / Scenario "通过 CLI 启动 DAG run"
  - Command: `uv run edera dag list --output json`
  - Expect: 返回合法 JSON，结构不变

### Task 2: 拆分 storage/repository.py 为 repository/ 子包

**Goal**: 将 1672 行的 `repository.py` 按聚合根拆分为 `repository/` 子包，`__init__.py` 全量 re-export 保持消费者零改动。

**Files**:
- Delete: `packages/core/src/edera_core/storage/repository.py`
- Create: `packages/core/src/edera_core/storage/repository/__init__.py`
- Create: `packages/core/src/edera_core/storage/repository/_entity_type.py`
- Create: `packages/core/src/edera_core/storage/repository/_core_entity.py`
- Create: `packages/core/src/edera_core/storage/repository/_ordinary.py`
- Create: `packages/core/src/edera_core/storage/repository/_relation.py`
- Create: `packages/core/src/edera_core/storage/repository/_skill.py`
- Create: `packages/core/src/edera_core/storage/repository/_extension.py`
- Create: `packages/core/src/edera_core/storage/repository/_log_index.py`
- Create: `packages/core/src/edera_core/storage/repository/_runtime.py`
- Create: `packages/core/src/edera_core/storage/repository/_helpers.py`

**Requirements**:
- `repository/__init__.py` re-export 所有公开 API，外部 `from edera_core.storage.repository import f` 不变
- 子模块间使用相对导入，依赖关系单向无环
- `_helpers.py` 不超过 200 行

#### Checks

- [ ] C1 验证 repository 公开 API 完整性
  - Preserves: `openspec/specs/entity-instance-crud-api/spec.md` / Requirement "Entity Instance CRUD API 适配三层存储路由" / Scenario "写入普通 entity"
  - Command: `uv run pytest tests/ -k "entity_repository or entity_store" -x --no-header -q 2>&1 | tail -3`
  - Expect: 测试全通过

- [ ] C2 验证消费者 import 无断裂
  - Preserves: `openspec/specs/entity-instance-crud-api/spec.md` / Requirement "Entity Instance CRUD API 适配三层存储路由" / Scenario "查询 entity 列表"
  - Command: `rg "from edera_core.storage.repository import" packages/ tests/ --files-with-matches | wc -l`
  - Expect: 所有消费者文件无需修改（import 路径不变）

- [ ] C3 验证核心实体 CRUD 行为不变
  - Preserves: `openspec/specs/entity-instance-crud-api/spec.md` / Requirement "Entity Instance CRUD API 适配三层存储路由" / Scenario "更新 entity 属性"
  - Command: `uv run pytest tests/ -k "core_entity or entity_crud" -x --no-header -q 2>&1 | tail -3`
  - Expect: 测试全通过

### Task 3: 提取 DagRunner 子组件

**Goal**: 将 `dag/runner.py` 的 sub-dag、循环、资源管理逻辑及模块级纯函数提取到独立模块，`DagRunner` 类保留主循环。

**Files**:
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Create: `packages/core/src/edera_core/dag/_subdag.py`
- Create: `packages/core/src/edera_core/dag/_loop.py`
- Create: `packages/core/src/edera_core/dag/_helpers.py`
- Modify: `packages/core/src/edera_core/dag/resources.py`

**Requirements**:
- Sub-dag 执行逻辑提取到 `_subdag.py`，通过函数委托调用
- 并行/串行循环提取到 `_loop.py`
- 10 个模块级纯函数提取到 `_helpers.py`
- 资源 acquire/release/wait 方法合并入 `resources.py`
- `DagRunner` 类名和公开方法签名不变，外部调用者不感知

#### Checks

- [ ] C1 验证 DAG 执行行为不变
  - Preserves: `openspec/specs/dag-runner/spec.md` / Requirement "NodeExecutor 使用 DagExecutionSnapshot 中的 handler resolver" / Scenario "DAG 正常运行"
  - Command: `uv run pytest tests/ -k "dag_runner" -x --no-header -q 2>&1 | tail -3`
  - Expect: 测试全通过

- [ ] C2 验证 sub-dag 执行行为不变
  - Preserves: `openspec/specs/dag-runner/spec.md` / Requirement "NodeExecutor 使用 DagExecutionSnapshot 中的 handler resolver" / Scenario "子 DAG 嵌套执行"
  - Command: `uv run pytest tests/ -k "subdag or sub_dag" -x --no-header -q 2>&1 | tail -3`
  - Expect: 测试全通过

- [ ] C3 验证资源信号量行为不变
  - Preserves: `openspec/specs/dag-resource-semaphore/spec.md` / Requirement "DAG 节点资源信号量约束" / Scenario "资源限制并发"
  - Command: `uv run pytest tests/core/integration/test_resource_semaphore.py -x --no-header -q 2>&1 | tail -3`
  - Expect: 测试全通过

### Task 4: 更新测试导入路径并删除 cli_help.py

**Goal**: 更新 7 个 CLI 测试文件的 import 路径，删除 `cli_help.py`，确保所有测试通过。

**Files**:
- Modify: `tests/core/unit/test_cli.py`
- Modify: `tests/core/unit/test_cli_extension.py`
- Modify: `packages/core/tests/test_cli_relation_aliases.py`
- Modify: `packages/core/tests/test_cli_skill.py`
- Modify: `packages/core/tests/test_bootstrap_with_existing_cert.py`
- Modify: `packages/core/tests/test_cli_entity.py`
- Modify: `packages/core/tests/test_cli_help.py`
- Delete: `packages/core/src/edera_core/cli_help.py`

**Requirements**:
- CLI 测试 import 从 `edera_core.cli` 改为 `edera_core.cli.<command>`
- `test_cli_help.py` 改为逐模块验证 HELP 常量
- `cli_help.py` 完全删除

#### Checks

- [ ] C1 验证 CLI 测试全通过
  - Preserves: `openspec/specs/edera-cli/spec.md` / Requirement "edera CLI 提供完整控制面子命令集" / Scenario "全部子命令 help 文本正确"
  - Command: `uv run pytest tests/core/unit/test_cli.py packages/core/tests/test_cli_entity.py packages/core/tests/test_cli_skill.py packages/core/tests/test_cli_relation_aliases.py packages/core/tests/test_cli_help.py tests/core/unit/test_cli_extension.py packages/core/tests/test_bootstrap_with_existing_cert.py -x --no-header -q 2>&1 | tail -3`
  - Expect: 测试全通过

- [ ] C2 验证 cli_help.py 已删除且无残留引用
  - Preserves: `openspec/specs/edera-cli/spec.md` / Requirement "edera CLI 提供完整控制面子命令集" / Scenario "子命令 help 文本包含 description"
  - Command: `rg "cli_help" packages/core/src/ tests/ --files-with-matches`
  - Expect: 无输出（无残留引用）

- [ ] C3 验证全量测试通过
  - Preserves: `openspec/specs/dag-runner/spec.md` / Requirement "NodeExecutor 使用 DagExecutionSnapshot 中的 handler resolver" / Scenario "DAG 正常运行"
  - Command: `uv run pytest tests/ packages/ -x --no-header -q 2>&1 | tail -5`
  - Expect: 所有测试通过（零回归）
