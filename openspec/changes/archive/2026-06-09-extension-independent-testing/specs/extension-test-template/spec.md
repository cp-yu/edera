## ADDED Requirements

### Requirement: 扩展测试模板必须提供 conftest.py.template

系统 SHALL 在 `extension-test-template/conftest.py.template` 中提供标准的 pytest fixtures 配置模板。

#### Scenario: 导入 edera-testing fixtures

- **WHEN** 扩展开发者使用 `conftest.py.template`
- **THEN** 模板 MUST 包含 `from edera_testing import extension_runtime, mock_pi_binary, mock_handler_context` 等导入语句

#### Scenario: 提供 extension_name 覆盖示例

- **WHEN** 扩展开发者需要覆盖自动推断的扩展名
- **THEN** 模板 MUST 包含注释示例：
  ```python
  # @pytest.fixture
  # def extension_name():
  #     return "your-extension-name"
  ```

### Requirement: 扩展测试模板必须提供 pytest.ini.template

系统 SHALL 在 `extension-test-template/pytest.ini.template` 中提供标准的 pytest 配置模板。

#### Scenario: 配置 asyncio 模式

- **WHEN** 扩展开发者使用 `pytest.ini.template`
- **THEN** 模板 MUST 包含 `asyncio_mode = auto`

#### Scenario: 配置测试路径

- **WHEN** 扩展开发者使用 `pytest.ini.template`
- **THEN** 模板 MUST 包含 `testpaths = tests`

#### Scenario: 配置测试文件模式

- **WHEN** 扩展开发者使用 `pytest.ini.template`
- **THEN** 模板 MUST 包含 `python_files = test_*.py`

### Requirement: 扩展测试模板必须提供 test_handler_unit.py.template

系统 SHALL 在 `extension-test-template/test_handler_unit.py.template` 中提供 handler 单元测试模板。

#### Scenario: 演示基础 handler 测试

- **WHEN** 扩展开发者查看单元测试模板
- **THEN** 模板 MUST 包含以下示例：
  - 测试 handler 基本调用
  - 测试参数传递（`params`、`input`）
  - 测试错误处理
  - 使用 `mock_handler_context` fixture

#### Scenario: 演示 handler 签名验证

- **WHEN** 扩展开发者查看单元测试模板
- **THEN** 模板 MUST 包含使用 `assert_handler_signature` 的示例

### Requirement: 扩展测试模板必须提供 test_dag_e2e.py.template

系统 SHALL 在 `extension-test-template/test_dag_e2e.py.template` 中提供 DAG E2E 测试模板。

#### Scenario: 演示扩展安装和配置加载

- **WHEN** 扩展开发者查看 E2E 测试模板
- **THEN** 模板 MUST 包含以下示例：
  - 使用 `extension_runtime` fixture
  - 验证 DAG 加载（`config.dags`）
  - 验证 Node 配置（`config.nodes`）
  - 验证 Entity Types（`config.entity_types`）

#### Scenario: 演示 mock agent 测试

- **WHEN** 扩展开发者查看 E2E 测试模板
- **THEN** 模板 MUST 包含使用 `mock_pi_binary` 创建 fake PI binary 的示例

#### Scenario: 演示 DAG 执行测试

- **WHEN** 扩展开发者查看 E2E 测试模板
- **THEN** 模板 MUST 包含以下示例：
  - 创建 `DagRunner` 和 `NodeExecutor`
  - 执行 DAG
  - 验证执行结果
  - 使用 mock handlers

### Requirement: 扩展测试模板必须提供 README.md

系统 SHALL 在 `extension-test-template/README.md` 中提供详细的使用指南。

#### Scenario: 说明目录结构要求

- **WHEN** 扩展开发者阅读 README.md
- **THEN** 文档 MUST 说明扩展测试必须放在 `extensions/*/tests/` 目录

#### Scenario: 说明如何使用模板

- **WHEN** 扩展开发者阅读 README.md
- **THEN** 文档 MUST 包含以下步骤：
  1. 复制模板文件到扩展的 `tests/` 目录
  2. 移除 `.template` 后缀
  3. 根据扩展需求调整模板内容
  4. 运行 `cd extensions/your-extension && pytest`

#### Scenario: 说明单元测试 vs E2E 测试的区别

- **WHEN** 扩展开发者阅读 README.md
- **THEN** 文档 MUST 说明：
  - 单元测试：测试 handler 逻辑、数据转换，不启动完整系统
  - E2E 测试：验证与 edera_core 的集成，需要安装扩展并运行 DAG

#### Scenario: 提供常见测试模式示例

- **WHEN** 扩展开发者阅读 README.md
- **THEN** 文档 MUST 包含以下测试模式的示例和说明：
  - Handler 测试（参数传递、错误处理）
  - DAG 拓扑测试（节点数量、边连接）
  - 资源约束测试（资源信号量）
  - Agent 节点测试（mock PI binary）

#### Scenario: 说明如何安装 edera-testing

- **WHEN** 扩展开发者阅读 README.md
- **THEN** 文档 MUST 包含安装命令：`pip install -e packages/edera-testing`

### Requirement: 扩展测试模板目录结构必须清晰

系统 SHALL 将所有模板文件组织在 `extension-test-template/` 目录下。

#### Scenario: 标准目录结构

- **WHEN** 扩展开发者浏览 `extension-test-template/` 目录
- **THEN** 目录结构 MUST 如下：
  ```
  extension-test-template/
  ├── README.md
  ├── conftest.py.template
  ├── pytest.ini.template
  ├── test_handler_unit.py.template
  └── test_dag_e2e.py.template
  ```
