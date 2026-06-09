## Why

当前扩展测试集中在 `tests/extensions/` 目录，与主项目测试耦合。这阻碍了扩展生态的发展——用户无法在独立仓库中开发和测试自己的扩展。我们需要建立扩展独立测试框架，提供可复用的测试基础设施，让每个扩展在自己的 `tests/` 目录下维护测试。

## What Changes

- **创建 edera-testing 包**：提供可复用的测试 fixtures、assertions 和 mocks，供所有扩展使用
- **创建扩展测试模板**：提供标准化的测试脚手架和使用指南
- **迁移现有扩展测试**：将 `tests/extensions/` 中的测试迁移到各扩展的 `tests/` 子目录
- **删除遗留代码**：移除 `llm.py` 及其测试（已被 Core 的 `_execute_agent` 替代）
- **删除冗余测试**：移除 `test_default_news_workflow.py`（core 已测试扩展安装能力）
- **更新测试发现规则**：主项目 pytest 配置为 `testpaths = ["tests"]`，不包含 extensions

## Capabilities

### New Capabilities

- `extension-testing-framework`: edera-testing 包，提供 fixtures（extension_runtime、mock_pi_binary、mock_handler_context、mock_entity_store）、assertions（assert_handler_signature、assert_manifest_valid）和 mocks（FakePIBinary、MockScript）
- `extension-test-template`: 扩展测试模板，包含 conftest.py.template、pytest.ini.template、test_handler_unit.py.template、test_dag_e2e.py.template 和详细的 README.md

### Modified Capabilities

无（这是新增测试基础设施，不修改现有功能的 requirements）

## Impact

**测试代码迁移：**
- `tests/extensions/test_legacy_script_adapter.py` (524 行) → `extensions/uzi-skill/tests/test_adapter.py`
- `tests/extensions/test_uzi_skill_dag.py` (588 行，删除配置测试部分) → `extensions/uzi-skill/tests/test_dag_e2e.py`
- `tests/extensions/test_extension_handlers.py` (36 行) → `extensions/default-news-workflow/tests/test_handlers.py`

**删除的文件：**
- `tests/extensions/test_default_news_workflow.py` (136 行)
- `tests/extensions/test_llm_runner.py` (268 行)
- `extensions/default-news-workflow/_lib/common/_lib/llm.py` (163 行)
- `tests/extensions/` 目录

**新增的包和目录：**
- `packages/edera-testing/` (新增测试框架包)
- `extension-test-template/` (新增测试模板)
- `extensions/uzi-skill/tests/` (新增扩展测试目录)
- `extensions/default-news-workflow/tests/` (新增扩展测试目录)

**主项目配置：**
- `pyproject.toml`: 确保 `testpaths = ["tests"]` 不包含 extensions

**CI/CD：**
- 主项目 CI 不运行扩展测试（扩展可在独立仓库中维护自己的 CI）
