## Context

当前 Edera 的扩展测试集中在 `tests/extensions/` 目录下，包含 1329 行测试代码（54 个测试函数）。这些测试与主项目测试基础设施紧密耦合，扩展开发者无法在独立仓库中开发和测试自己的扩展。

**现有测试分布：**
- `test_default_news_workflow.py` (136 行)：测试扩展安装和配置加载
- `test_extension_handlers.py` (36 行)：测试 7 个 provider handlers 的函数签名契约
- `test_legacy_script_adapter.py` (524 行)：测试 uzi-skill 的 LegacyScriptAdapter 逻辑
- `test_llm_runner.py` (268 行)：测试 `_lib/common/_lib/llm.py` 的 LLM 运行时
- `test_uzi_skill_dag.py` (588 行)：测试 uzi-skill 的 DAG 拓扑、资源约束和端到端执行

**关键发现：**
- Core 已在 `tests/core/unit/test_extension_*.py` 中测试扩展管理能力（1175+ 行）
- `llm.py` 的 `run_pi` 函数无任何调用者（已被 Core 的 `NodeExecutor._execute_agent` 替代）
- 扩展测试需要完整的 core 基础设施（ExtensionManager、DagRunner、数据库初始化）

**约束：**
- 必须支持独立仓库中的用户扩展
- 主项目 CI 不运行扩展测试（快速反馈）
- 官方扩展（uzi-skill、default-news-workflow）保留全量 E2E 测试（确保完整性）

## Goals / Non-Goals

**Goals:**
- 每个扩展在自己的 `tests/` 子目录下维护测试
- 提供 `edera-testing` 包，封装可复用的测试工具
- 提供扩展测试模板和详细使用指南
- 约定优于配置：扩展测试必须放在 `extensions/*/tests/` 目录
- 支持扩展独立运行：`cd extensions/xxx && pytest`

**Non-Goals:**
- 不改变 Core 的测试架构（`tests/core/` 保持不变）
- 不提供扩展之间的集成测试能力（每个扩展独立测试）
- 不自动发现和运行扩展测试（主项目 pytest 不包含 extensions）

## Decisions

### 决策 1: edera-testing 作为独立包

**选择：** 创建 `packages/edera-testing/` 独立包，强依赖 `edera-core`

**理由：**
- 职责分离：core 是业务逻辑，testing 是测试基础设施
- 可选依赖：生产环境不需要安装 edera-testing
- 独立版本：testing 可以独立演进，新增 fixtures 不影响 core 版本
- 清晰的依赖关系：`edera-testing` depends on `edera-core`，而不是反向

**备选方案（已拒绝）：**
- 作为 `edera_core.testing` 子模块：会污染 core 的依赖（pytest 等测试工具）
- 弱依赖（通过 extras）：增加复杂度，扩展 E2E 测试必然依赖 core

### 决策 2: 测试归属粒度

**选择：** 扁平化，workflow 级测试

**示例：**
```
extensions/default-news-workflow/
└── tests/                    # workflow 级测试
    ├── conftest.py
    ├── pytest.ini
    └── test_handlers.py      # 所有 7 个 provider 的契约测试
```

**理由：**
- `_providers` 不是独立分发的扩展，只是内部组织方式
- 每个 provider 只有一个 `handler.py`，测试代码量小（7 个 provider 共 36 行测试）
- 避免过度嵌套，保持简单

**备选方案（已拒绝）：**
- 每个 provider 独立测试目录：过度嵌套，每个 provider 测试少于 10 行

### 决策 3: E2E 测试粒度

**选择：** 保留全量 E2E 测试

**理由：**
- 用户明确要求：持续验证扩展在 core 升级后仍能运行
- 官方扩展（uzi-skill、default-news-workflow）作为示例和 smoke test
- 扩展测试较重可接受（依赖完整 core 基础设施），因为不在主项目 CI 中运行

**影响：**
- 每个 E2E 测试需要 init DB、install extension、run DAG
- 依赖 ExtensionManager、DagRunner、NodeExecutor 等完整基础设施

### 决策 4: 测试基础设施设计

**选择：** 框架（edera-testing 包）+ 模板（extension-test-template）

**edera-testing 包结构：**
```python
# packages/edera-testing/src/edera_testing/

# fixtures.py
@pytest.fixture
async def extension_runtime(tmp_path, extension_name):
    """自动安装扩展并返回 runtime config
    
    extension_name 传递方式：
    - 自动推断：从测试文件路径提取（extensions/uzi-skill/tests/ → "uzi-skill"）
    - 可覆盖：扩展的 conftest.py 提供 extension_name fixture
    """
    ...

@pytest.fixture
def mock_pi_binary(tmp_path):
    """创建 fake PI binary，返回路径"""
    ...

@pytest.fixture
def mock_handler_context():
    """创建标准的 HandlerContext mock"""
    ...

# assertions.py
def assert_handler_signature(module):
    """验证 handler.py 的 run() 函数签名"""
    assert len(inspect.signature(module.run).parameters) == 1

def assert_manifest_valid(manifest_path):
    """验证 manifest.yaml 格式"""
    ...

# mocks.py
class FakePIBinary:
    """Fake PI binary for agent node testing"""
    ...

class MockScript:
    """Mock handler script for testing"""
    ...
```

**理由：**
- 减少样板代码：当前两个测试文件都有相同的 `_runtime_config` helper
- 保证测试质量一致性：统一的 fixture 和 assertions
- 降低扩展开发者门槛：直接 `from edera_testing import ...` 即可

**备选方案（已拒绝）：**
- 轻量级模板（仅文件模板）：扩展开发者需要复制和维护重复的测试工具代码

### 决策 5: 测试发现规则

**选择：** 约定优于配置

**规则：**
- 扩展测试**必须**放在 `extensions/*/tests/` 目录
- 主项目 `pyproject.toml` 配置：`testpaths = ["tests"]`（不包含 extensions）
- 扩展独立运行：`cd extensions/xxx && pytest`

**理由：**
- 简单：无需 manifest 配置或自定义 pytest 插件
- 明确：扩展开发者清楚知道测试应该放在哪里
- 符合 Python 社区惯例（`tests/` 目录）

**备选方案（已拒绝）：**
- 在 manifest.yaml 中声明测试路径：需要实现自定义 pytest 插件，复杂度高
- 主项目 pytest 自动发现扩展测试：违反"主项目 CI 不运行扩展测试"的约束

### 决策 6: llm.py 处理

**选择：** 删除 `extensions/default-news-workflow/_lib/common/_lib/llm.py` 和 `test_llm_runner.py`

**理由：**
- Core 已经有完整的 Agent 节点实现（`NodeExecutor._execute_agent`）
- llm.py 的 `run_pi` 无任何调用者（grep 证实）
- 所有扩展都使用标准的 `type: agent` 节点配置
- 这是在 agent 系统重构后（commit 4ea1a17, fbb4b2e）的遗留代码

**对比：**
| 特性 | Core `_execute_agent` | Extension `llm.py::run_pi` |
|------|----------------------|---------------------------|
| 用途 | 标准 Agent 节点执行 | ~~handler 内部调用 PI~~（实际无人使用） |
| Prompt | 通过 `--model` + prompt file | 直接传递 JSON input |
| Skills | 动态生成到 session_dir | 手动传递 `--skill` 参数 |
| 证书 | 从 certificate issuer | 无 |

### 决策 7: 测试迁移策略

**选择：** 大爆炸迁移（单个 mega PR，分 5 个逻辑 commits）

**Commit 顺序：**
1. 创建 edera-testing 包（实现 fixtures、assertions、mocks）
2. 创建扩展测试模板（README、conftest.py.template、pytest.ini.template、test_*.template）
3. 迁移 uzi-skill 测试（test_adapter.py、test_dag_e2e.py）
4. 迁移 default-news-workflow 测试（test_handlers.py）
5. 清理旧测试和遗留代码（删除 tests/extensions/、llm.py）

**理由：**
- 便于 review：逻辑上分步，实际上在一个 PR 中
- 可回滚：每个 commit 是独立的逻辑单元
- 原子性：避免中间状态（部分测试在旧位置，部分在新位置）

## Risks / Trade-offs

### 风险 1: 扩展测试可能在 core 升级后 break

**影响：** 主 CI 不运行扩展测试，core 变更可能破坏扩展测试而不被发现

**缓解措施：**
- 官方扩展（uzi-skill、default-news-workflow）作为 smoke test，定期手动运行
- edera-testing 包版本与 edera-core 同步发布
- 扩展测试模板保持最新，反映最佳实践

### 风险 2: 扩展 E2E 测试较重

**影响：** 依赖完整 core 基础设施，测试启动慢

**权衡：** 可接受，因为：
- 扩展测试不在主项目 CI 中运行，不影响主项目反馈速度
- E2E 测试确保扩展完整性，价值高于成本

### 风险 3: 测试代码可能重复

**影响：** 不同扩展可能编写相似的测试工具函数

**缓解措施：**
- edera-testing 包提供通用 fixtures 和工具
- 扩展测试模板提供最佳实践示例
- 发现重复模式时，提取到 edera-testing 包

### 风险 4: 迁移过程中可能遗漏测试

**影响：** 大量测试代码迁移，可能遗漏部分测试函数

**缓解措施：**
- 迁移前后统计测试函数数量（当前 54 个）
- 每个迁移 commit 独立验证测试通过
- Code review 检查迁移映射表

### Trade-off: edera-testing 包维护成本

**权衡：** 增加了一个新包的维护成本（版本管理、兼容性、文档）

**收益：** 降低了扩展开发者的门槛，促进扩展生态发展

### Trade-off: 约定优于配置的灵活性

**权衡：** 强制扩展测试放在 `extensions/*/tests/` 目录，缺乏灵活性

**收益：** 简单清晰，无需额外配置或插件，符合 Python 社区惯例
