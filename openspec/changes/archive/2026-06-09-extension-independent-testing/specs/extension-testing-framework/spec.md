## ADDED Requirements

### Requirement: edera-testing 包必须提供 extension_runtime fixture

系统 SHALL 提供 `extension_runtime` fixture，自动安装指定扩展并返回 runtime config。

#### Scenario: 自动推断扩展名

- **WHEN** 测试文件位于 `extensions/uzi-skill/tests/test_adapter.py`
- **THEN** `extension_runtime` fixture 自动推断扩展名为 `"uzi-skill"`

#### Scenario: 通过 conftest.py 覆盖扩展名

- **WHEN** 扩展的 `conftest.py` 定义 `extension_name` fixture 返回 `"custom-name"`
- **THEN** `extension_runtime` fixture 使用 `"custom-name"` 而非自动推断的名称

#### Scenario: 自动初始化测试环境

- **WHEN** 测试调用 `extension_runtime` fixture
- **THEN** 系统 SHALL 自动执行以下操作：
  - 创建临时数据库（`tmp_path / "runtime.db"`）
  - 调用 `init_db(engine)`
  - 调用 `ExtensionManager.install(extension_name, installed_by="test")`
  - 调用 `load_runtime_app_config(Path("config"), engine, [Path("extensions")])`
  - 在测试结束后自动 `engine.dispose()`

#### Scenario: 返回 RuntimeConfig

- **WHEN** 测试调用 `extension_runtime` fixture
- **THEN** 返回值 MUST 是 `RuntimeConfig` 对象，包含 `dags`、`nodes`、`entity_types`、`system`、`runtime` 等字段

### Requirement: edera-testing 包必须提供 mock_pi_binary fixture

系统 SHALL 提供 `mock_pi_binary` fixture，创建 fake PI binary 用于测试 agent 节点。

#### Scenario: 创建可执行的 fake binary

- **WHEN** 测试调用 `mock_pi_binary(tmp_path)` 并传入自定义脚本内容
- **THEN** 返回可执行文件路径，且文件具有可执行权限（`0o755`）

#### Scenario: 捕获 PI 调用参数

- **WHEN** fake PI binary 被 NodeExecutor 调用
- **THEN** fake binary MUST 能够捕获 `sys.argv`、`os.getcwd()`、`os.environ` 等上下文信息

### Requirement: edera-testing 包必须提供 mock_handler_context fixture

系统 SHALL 提供 `mock_handler_context` fixture，创建标准的 `HandlerContext` mock。

#### Scenario: 提供默认的 HandlerContext

- **WHEN** 测试调用 `mock_handler_context()`
- **THEN** 返回 `HandlerContext` 对象，包含 `input`、`params`、`node_name`、`node_type`、`run_id`、`entity_store`、`storage`、`runtime` 等字段

#### Scenario: 支持自定义字段

- **WHEN** 测试调用 `mock_handler_context(params={"key": "value"}, run_id="run-123")`
- **THEN** 返回的 `HandlerContext` MUST 使用传入的自定义值

### Requirement: edera-testing 包必须提供 assert_handler_signature 断言

系统 SHALL 提供 `assert_handler_signature(module)` 函数，验证 handler 的 `run()` 函数签名符合契约。

#### Scenario: 验证单参数签名

- **WHEN** handler 模块的 `run()` 函数接受 1 个参数（`HandlerContext`）
- **THEN** `assert_handler_signature(module)` 不抛出异常

#### Scenario: 拒绝多参数签名

- **WHEN** handler 模块的 `run()` 函数接受 2 个或更多参数
- **THEN** `assert_handler_signature(module)` MUST 抛出 `AssertionError`

### Requirement: edera-testing 包必须提供 assert_manifest_valid 断言

系统 SHALL 提供 `assert_manifest_valid(manifest_path)` 函数，验证 `manifest.yaml` 格式正确。

#### Scenario: 验证必需字段

- **WHEN** `manifest.yaml` 包含 `name`、`version`、`handlers` 字段
- **THEN** `assert_manifest_valid(manifest_path)` 不抛出异常

#### Scenario: 拒绝缺失必需字段

- **WHEN** `manifest.yaml` 缺少 `name` 或 `version` 字段
- **THEN** `assert_manifest_valid(manifest_path)` MUST 抛出 `AssertionError`

### Requirement: edera-testing 包必须提供 FakePIBinary 类

系统 SHALL 提供 `FakePIBinary` 类，用于创建可配置的 fake PI binary。

#### Scenario: 配置返回值

- **WHEN** 测试创建 `FakePIBinary(output={"result": "success"})`
- **THEN** fake binary 执行时 MUST 输出指定的 JSON 到 stdout

#### Scenario: 配置退出码

- **WHEN** 测试创建 `FakePIBinary(exit_code=1)`
- **THEN** fake binary 执行时 MUST 以退出码 1 退出

### Requirement: edera-testing 包必须提供 MockScript 类

系统 SHALL 提供 `MockScript` 类，用于创建 mock handler script。

#### Scenario: 模拟简单返回值

- **WHEN** 测试创建 `MockScript` 并定义 `main(ticker)` 函数返回 `{"ticker": ticker}`
- **THEN** LegacyScriptAdapter 调用该 script 时 MUST 返回指定的 payload

### Requirement: edera-testing 包必须强依赖 edera-core

系统 SHALL 在 `pyproject.toml` 中声明 `edera-core>=0.1.0` 作为强依赖。

#### Scenario: 安装 edera-testing 自动安装 edera-core

- **WHEN** 用户执行 `pip install edera-testing`
- **THEN** pip MUST 自动安装 `edera-core`、`edera-types`、`pytest`、`pytest-asyncio`

### Requirement: 系统必须提供扩展测试文档

系统 SHALL 在 `docs/testing/extension-testing-guide.md` 提供扩展测试完整指南。

#### Scenario: 文档说明测试目录结构约定

- **WHEN** 扩展开发者阅读 `docs/testing/extension-testing-guide.md`
- **THEN** 文档 MUST 说明扩展测试必须放在 `extensions/<extension-name>/tests/` 目录

#### Scenario: 文档说明如何使用 edera-testing 框架

- **WHEN** 扩展开发者阅读 `docs/testing/extension-testing-guide.md`
- **THEN** 文档 MUST 包含以下内容：
  - 安装 edera-testing 包的步骤
  - 使用 `extension_runtime`、`mock_pi_binary`、`mock_handler_context` 等 fixtures 的示例
  - 单元测试 vs E2E 测试的区别和最佳实践
  - 常见测试模式（handler 测试、DAG 测试、资源测试、agent 测试）

#### Scenario: 文档说明如何独立运行扩展测试

- **WHEN** 扩展开发者阅读 `docs/testing/extension-testing-guide.md`
- **THEN** 文档 MUST 说明如何在扩展目录内独立运行测试：`cd extensions/<extension-name> && pytest`

#### Scenario: 文档引用扩展测试模板

- **WHEN** 扩展开发者阅读 `docs/testing/extension-testing-guide.md`
- **THEN** 文档 MUST 引用 `extension-test-template/` 目录作为实际可用的模板文件
