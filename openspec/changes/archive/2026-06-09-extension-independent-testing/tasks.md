### Task 1: 创建 edera-testing 包结构

**Goal**: 创建 edera-testing 独立包，包含 pyproject.toml 和基础目录结构。

**Files**:
- Create: `packages/edera-testing/pyproject.toml`
- Create: `packages/edera-testing/src/edera_testing/__init__.py`
- Create: `packages/edera-testing/README.md`

**Requirements**:
- 声明包名为 `edera-testing`，版本 `0.1.0`
- 强依赖 `edera-core>=0.1.0`、`edera-types>=0.1.0`、`pytest>=8.0.0`、`pytest-asyncio>=0.23.0`
- 导出所有公开 API

#### Checks

- [x] C1 验证包结构

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须强依赖 edera-core" / Scenario "安装 edera-testing 自动安装 edera-core"
  - Evidence: `packages/edera-testing/pyproject.toml` 中的 `dependencies` 字段
  - Expect: 包含 `edera-core>=0.1.0`、`edera-types>=0.1.0`、`pytest>=8.0.0`、`pytest-asyncio>=0.23.0`

- [x] C2 验证包可安装

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须强依赖 edera-core" / Scenario "安装 edera-testing 自动安装 edera-core"
  - Command: `pip install -e packages/edera-testing`
  - Expect: 安装成功且 `pip list` 显示 `edera-testing` 和 `edera-core`

### Task 2: 实现 extension_runtime fixture

**Goal**: 实现核心 fixture，自动安装扩展并返回 runtime config。

**Files**:
- Create: `packages/edera-testing/src/edera_testing/fixtures.py`
- Test: `packages/edera-testing/tests/test_fixtures.py`

**Requirements**:
- 自动推断扩展名（从测试文件路径）
- 支持通过 conftest.py 覆盖扩展名
- 自动初始化测试环境（创建 DB、安装扩展、加载配置）
- 测试结束后自动清理
- 返回 RuntimeConfig 对象

#### Checks

- [x] C3 验证自动推断扩展名

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 extension_runtime fixture" / Scenario "自动推断扩展名"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_auto_infer_extension_name`
  - Expect: 测试通过，从路径 `extensions/test-ext/tests/test_foo.py` 推断出 `"test-ext"`

- [x] C4 验证 conftest.py 覆盖

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 extension_runtime fixture" / Scenario "通过 conftest.py 覆盖扩展名"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_override_extension_name`
  - Expect: 测试通过，使用 conftest.py 提供的扩展名而非自动推断的名称

- [x] C5 验证自动初始化测试环境

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 extension_runtime fixture" / Scenario "自动初始化测试环境"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_extension_runtime_initialization`
  - Expect: 测试通过，验证 DB 创建、扩展安装、配置加载、自动清理

- [x] C6 验证返回 RuntimeConfig

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 extension_runtime fixture" / Scenario "返回 RuntimeConfig"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_extension_runtime_returns_config`
  - Expect: 测试通过，返回值包含 `dags`、`nodes`、`entity_types` 等字段

### Task 3: 实现 mock_pi_binary 和 mock_handler_context fixtures

**Goal**: 实现 mock 工具 fixtures。

**Files**:
- Modify: `packages/edera-testing/src/edera_testing/fixtures.py`
- Test: `packages/edera-testing/tests/test_fixtures.py`

**Requirements**:
- `mock_pi_binary` 创建可执行的 fake PI binary
- `mock_handler_context` 创建标准的 HandlerContext mock
- 支持自定义字段

#### Checks

- [x] C7 验证 fake PI binary 可执行

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 mock_pi_binary fixture" / Scenario "创建可执行的 fake binary"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_mock_pi_binary_executable`
  - Expect: 测试通过，fake binary 具有可执行权限且可被调用

- [x] C8 验证 fake PI binary 捕获参数

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 mock_pi_binary fixture" / Scenario "捕获 PI 调用参数"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_mock_pi_binary_captures_context`
  - Expect: 测试通过，fake binary 能够捕获 argv、cwd、environ

- [x] C9 验证 HandlerContext mock

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 mock_handler_context fixture" / Scenario "提供默认的 HandlerContext"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_mock_handler_context_default`
  - Expect: 测试通过，返回包含所有必需字段的 HandlerContext

- [x] C10 验证 HandlerContext 自定义字段

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 mock_handler_context fixture" / Scenario "支持自定义字段"
  - Command: `pytest packages/edera-testing/tests/test_fixtures.py::test_mock_handler_context_custom`
  - Expect: 测试通过，自定义字段被正确应用

### Task 4: 实现 assertions 工具

**Goal**: 实现断言工具函数。

**Files**:
- Create: `packages/edera-testing/src/edera_testing/assertions.py`
- Test: `packages/edera-testing/tests/test_assertions.py`

**Requirements**:
- `assert_handler_signature` 验证 handler 签名
- `assert_manifest_valid` 验证 manifest.yaml 格式

#### Checks

- [x] C11 验证单参数签名

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 assert_handler_signature 断言" / Scenario "验证单参数签名"
  - Command: `pytest packages/edera-testing/tests/test_assertions.py::test_assert_handler_signature_valid`
  - Expect: 测试通过，接受 1 个参数的 handler 不抛出异常

- [x] C12 验证拒绝多参数签名

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 assert_handler_signature 断言" / Scenario "拒绝多参数签名"
  - Command: `pytest packages/edera-testing/tests/test_assertions.py::test_assert_handler_signature_invalid`
  - Expect: 测试通过，接受多个参数的 handler 抛出 AssertionError

- [x] C13 验证 manifest 必需字段

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 assert_manifest_valid 断言" / Scenario "验证必需字段"
  - Command: `pytest packages/edera-testing/tests/test_assertions.py::test_assert_manifest_valid_complete`
  - Expect: 测试通过，包含所有必需字段的 manifest 不抛出异常

- [x] C14 验证拒绝缺失字段

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 assert_manifest_valid 断言" / Scenario "拒绝缺失必需字段"
  - Command: `pytest packages/edera-testing/tests/test_assertions.py::test_assert_manifest_valid_missing_fields`
  - Expect: 测试通过，缺失必需字段的 manifest 抛出 AssertionError

### Task 5: 实现 mocks 类

**Goal**: 实现 FakePIBinary 和 MockScript 类。

**Files**:
- Create: `packages/edera-testing/src/edera_testing/mocks.py`
- Test: `packages/edera-testing/tests/test_mocks.py`

**Requirements**:
- `FakePIBinary` 支持配置返回值和退出码
- `MockScript` 支持模拟 handler script
- 提供清晰的 API

#### Checks

- [x] C15 验证 FakePIBinary 配置返回值

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 FakePIBinary 类" / Scenario "配置返回值"
  - Command: `pytest packages/edera-testing/tests/test_mocks.py::test_fake_pi_binary_output`
  - Expect: 测试通过，fake binary 输出指定的 JSON

- [x] C16 验证 FakePIBinary 配置退出码

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 FakePIBinary 类" / Scenario "配置退出码"
  - Command: `pytest packages/edera-testing/tests/test_mocks.py::test_fake_pi_binary_exit_code`
  - Expect: 测试通过，fake binary 以指定退出码退出

- [x] C17 验证 MockScript

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "edera-testing 包必须提供 MockScript 类" / Scenario "模拟简单返回值"
  - Command: `pytest packages/edera-testing/tests/test_mocks.py::test_mock_script`
  - Expect: 测试通过，mock script 返回指定的 payload

### Task 6: 创建扩展测试文档

**Goal**: 创建扩展测试完整指南文档。

**Files**:
- Create: `docs/testing/extension-testing-guide.md`

**Requirements**:
- 说明扩展测试必须放在 `extensions/<extension-name>/tests/` 目录
- 包含 edera-testing 框架的使用示例
- 说明单元测试 vs E2E 测试的区别
- 包含常见测试模式示例
- 说明如何独立运行扩展测试

#### Checks

- [x] C18 验证文档说明测试目录结构

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "系统必须提供扩展测试文档" / Scenario "文档说明测试目录结构约定"
  - Evidence: `docs/testing/extension-testing-guide.md`
  - Expect: 说明扩展测试必须放在 `extensions/<extension-name>/tests/` 目录

- [x] C19 验证文档说明框架使用

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "系统必须提供扩展测试文档" / Scenario "文档说明如何使用 edera-testing 框架"
  - Evidence: `docs/testing/extension-testing-guide.md`
  - Expect: 包含安装步骤、fixtures 示例、测试模式说明

- [x] C20 验证文档说明独立运行

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "系统必须提供扩展测试文档" / Scenario "文档说明如何独立运行扩展测试"
  - Evidence: `docs/testing/extension-testing-guide.md`
  - Expect: 说明 `cd extensions/<extension-name> && pytest` 命令

- [x] C21 验证文档引用模板

  - Verifies: `specs/extension-testing-framework/spec.md` / Requirement "系统必须提供扩展测试文档" / Scenario "文档引用扩展测试模板"
  - Evidence: `docs/testing/extension-testing-guide.md`
  - Expect: 引用 `extension-test-template/` 目录

### Task 7: 创建扩展测试模板

**Goal**: 创建标准化的扩展测试模板文件。

**Files**:
- Create: `extension-test-template/README.md`
- Create: `extension-test-template/conftest.py.template`
- Create: `extension-test-template/pytest.ini.template`
- Create: `extension-test-template/test_handler_unit.py.template`
- Create: `extension-test-template/test_dag_e2e.py.template`

**Requirements**:
- 提供详细的 README.md 使用指南
- 模板文件包含注释和示例
- 符合 edera-testing 框架的最佳实践

#### Checks

- [x] C22 验证 conftest.py.template

  - Verifies: `specs/extension-test-template/spec.md` / Requirement "扩展测试模板必须提供 conftest.py.template" / Scenario "导入 edera-testing fixtures"
  - Evidence: `extension-test-template/conftest.py.template`
  - Expect: 包含 `from edera_testing import` 导入语句

- [x] C23 验证 pytest.ini.template

  - Verifies: `specs/extension-test-template/spec.md` / Requirement "扩展测试模板必须提供 pytest.ini.template" / Scenario "配置 asyncio 模式"
  - Evidence: `extension-test-template/pytest.ini.template`
  - Expect: 包含 `asyncio_mode = auto` 和 `testpaths = tests`

- [x] C24 验证 test_handler_unit.py.template

  - Verifies: `specs/extension-test-template/spec.md` / Requirement "扩展测试模板必须提供 test_handler_unit.py.template" / Scenario "演示基础 handler 测试"
  - Evidence: `extension-test-template/test_handler_unit.py.template`
  - Expect: 包含 handler 调用、参数传递、错误处理的示例

- [x] C25 验证 test_dag_e2e.py.template

  - Verifies: `specs/extension-test-template/spec.md` / Requirement "扩展测试模板必须提供 test_dag_e2e.py.template" / Scenario "演示扩展安装和配置加载"
  - Evidence: `extension-test-template/test_dag_e2e.py.template`
  - Expect: 包含使用 `extension_runtime` fixture 和验证 DAG 加载的示例

- [x] C26 验证 README.md

  - Verifies: `specs/extension-test-template/spec.md` / Requirement "扩展测试模板必须提供 README.md" / Scenario "说明目录结构要求"
  - Evidence: `extension-test-template/README.md`
  - Expect: 说明扩展测试必须放在 `extensions/*/tests/` 目录

### Task 8: 迁移 uzi-skill 测试

**Goal**: 将 uzi-skill 相关测试迁移到扩展目录。

**Files**:
- Create: `extensions/uzi-skill/tests/conftest.py`
- Create: `extensions/uzi-skill/tests/pytest.ini`
- Create: `extensions/uzi-skill/tests/test_adapter.py`
- Create: `extensions/uzi-skill/tests/test_dag_e2e.py`

**Requirements**:
- 从 `tests/extensions/test_legacy_script_adapter.py` 迁移 20 个测试到 `test_adapter.py`
- 从 `tests/extensions/test_uzi_skill_dag.py` 迁移 E2E 测试（删除配置测试部分）到 `test_dag_e2e.py`
- 使用 edera-testing 框架的 fixtures

#### Checks

- [x] C27 验证 uzi-skill adapter 测试

  - Verifies: 非 spec 变更，验证迁移正确性
  - Command: `cd extensions/uzi-skill && pytest tests/test_adapter.py`
  - Expect: 所有 20 个 adapter 测试通过

- [x] C28 验证 uzi-skill DAG E2E 测试

  - Verifies: 非 spec 变更，验证迁移正确性
  - Command: `cd extensions/uzi-skill && pytest tests/test_dag_e2e.py`
  - Expect: 所有 E2E 测试通过（约 8 个测试）

### Task 9: 迁移 default-news-workflow 测试

**Goal**: 将 default-news-workflow 相关测试迁移到扩展目录。

**Files**:
- Create: `extensions/default-news-workflow/tests/conftest.py`
- Create: `extensions/default-news-workflow/tests/pytest.ini`
- Create: `extensions/default-news-workflow/tests/test_handlers.py`

**Requirements**:
- 从 `tests/extensions/test_extension_handlers.py` 提取 handler 签名测试逻辑
- 使用 edera-testing 的 `assert_handler_signature`

#### Checks

- [x] C29 验证 default-news-workflow handler 测试

  - Verifies: 非 spec 变更，验证迁移正确性
  - Command: `cd extensions/default-news-workflow && pytest tests/test_handlers.py`
  - Expect: handler 签名测试通过（7 个 providers）

### Task 10: 清理旧测试和遗留代码

**Goal**: 删除旧的集中测试目录和遗留的 llm.py 代码。

**Files**:
- Delete: `tests/extensions/test_default_news_workflow.py`
- Delete: `tests/extensions/test_extension_handlers.py`
- Delete: `tests/extensions/test_legacy_script_adapter.py`
- Delete: `tests/extensions/test_llm_runner.py`
- Delete: `tests/extensions/test_uzi_skill_dag.py`
- Delete: `extensions/default-news-workflow/_lib/common/_lib/llm.py`
- Modify: `pyproject.toml`

**Requirements**:
- 删除 `tests/extensions/` 目录下的所有测试文件
- 删除 `llm.py` 及其测试
- 确保主项目 `pyproject.toml` 的 `testpaths = ["tests"]`

#### Checks

- [x] C30 验证旧测试目录已删除

  - Verifies: 非 spec 变更，验证清理完成
  - Command: `test ! -d tests/extensions`
  - Expect: 目录不存在

- [x] C31 验证 llm.py 已删除

  - Verifies: 非 spec 变更，验证清理完成
  - Command: `test ! -f extensions/default-news-workflow/_lib/common/_lib/llm.py`
  - Expect: 文件不存在

- [x] C32 验证主项目测试配置

  - Verifies: 非 spec 变更，验证配置正确
  - Evidence: `pyproject.toml` 中的 `testpaths` 配置
  - Expect: `testpaths = ["tests"]`，不包含 extensions

- [x] C33 验证主项目测试仍然通过

  - Verifies: 非 spec 变更，验证清理后主项目测试无影响
  - Command: `pytest tests/`
  - Expect: 主项目所有测试通过
