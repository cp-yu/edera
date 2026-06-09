# 扩展测试指南

扩展测试必须放在 `extensions/<extension-name>/tests/` 目录。扩展可以在自己的目录中独立运行测试：

```bash
cd extensions/<extension-name> && pytest
```

安装测试框架：

```bash
pip install -e packages/edera-testing
```

## 基础配置

`conftest.py` 通常只需要导入框架 fixtures：

```python
from edera_testing import extension_runtime, mock_handler_context, mock_pi_binary
```

如果测试目录无法按 `extensions/<extension-name>/tests/` 推断扩展名，可以覆盖：

```python
import pytest


@pytest.fixture
def extension_name():
    return "your-extension-name"
```

`pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
```

## 单元测试和 E2E 测试

单元测试验证 handler 逻辑、参数传递和错误处理，不启动完整 runtime。使用 `mock_handler_context` 和 `assert_handler_signature`：

```python
from edera_testing import assert_handler_signature


def test_handler_signature(handler_module):
    assert_handler_signature(handler_module)


async def test_handler_params(mock_handler_context):
    ctx = mock_handler_context(params={"ticker": "00100.HK"})
    result = await handler_module.run(ctx)
    assert result["ticker"] == "00100.HK"
```

E2E 测试验证扩展安装、DAG 加载、资源约束和 agent 节点。使用 `extension_runtime`：

```python
async def test_dag_loaded(extension_runtime):
    assert "default" in extension_runtime.dags
    assert extension_runtime.nodes
    assert extension_runtime.entity_types
```

Agent 节点测试使用 `mock_pi_binary` 创建 fake PI binary：

```python
def test_agent_binary(mock_pi_binary):
    pi = mock_pi_binary()
    assert pi.exists()
```

## 模板

`extension-test-template/` 提供可复制的模板：

- `conftest.py.template`
- `pytest.ini.template`
- `test_handler_unit.py.template`
- `test_dag_e2e.py.template`

复制模板到扩展的 `tests/` 目录，移除 `.template` 后缀，再按扩展需求调整。
