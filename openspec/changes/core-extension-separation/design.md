## Context

当前 `src/stockimformation/` 是单一 Python 包，核心引擎（DAG runner、Node executor、Entity Store、Trigger）与业务逻辑（RSS 抓取、LLM 分析、建议生成）共存。`pipeline.py:_build_executor` 硬编码 handler 注册，`node/executor.py` 通过 `inspect.signature` 适配多种 handler 签名，并内嵌 `_run_pi` LLM 执行逻辑。

项目处于开发阶段，无生产用户，无历史负担。目标是为未来 Rust 核心重写奠定架构基础。

## Goals / Non-Goals

**Goals:**
- 核心引擎完全领域无关，不包含任何股票/RSS/建议等业务概念
- 扩展通过 manifest 声明式注册，添加新能力不修改核心代码
- 核心与扩展通过轻量接口包（`stockimformation-types`）解耦
- 统一 handler 调用协议为单参数 `HandlerContext`
- 为未来 Rust 核心重写提供清晰的 FFI 边界

**Non-Goals:**
- 本次不实现 Rust 重写，仅完成 Python 层面的架构分离
- 不改变用户可见的功能行为（DAG 执行结果、API 响应不变）
- 不重构前端代码，仅移动目录位置
- 不引入第三方插件分发机制（PyPI 发布等）

## Decisions

### D1: uv workspace monorepo 包结构

```
packages/
├── core/pyproject.toml          → stockimformation-core
└── core-types/pyproject.toml    → stockimformation-types
```

**理由**: 独立包边界使 core-types 可单独安装，扩展开发不依赖核心实现。uv workspace 提供统一的依赖解析和开发体验。

**备选**: 单包内部分层 — 放弃，因为无法实现扩展只依赖接口包的目标。

### D2: 统一 function node，移除 LLM executor

所有节点统一为 function node。原 LLM 节点的 `_run_pi`、`_prepare_workspace` 逻辑移入 `extensions/_lib/llm.py`，由 reader 等扩展内部调用。

**理由**: 核心不应知道 LLM 的存在。"调用 LLM"与"调用 HTTP API"对核心而言无区别，都是 handler 内部实现。核心越小，Rust 重写范围越小。

**备选**: 核心内置双执行器（function + llm）— 放弃，增加核心复杂度且 LLM 调用方式可能频繁变化。

### D3: Handler 签名统一为 `async def run(ctx: HandlerContext) -> Any`

`HandlerContext` 包含：`input: NodeInput`、`params: dict`、`node_name: str`、`node_type: str`、`cycle_id: str`、`entity_store: EntityStoreProtocol`。

**理由**: 单参数签名面向未来不破坏（新增字段不改签名），对 Rust FFI 友好（传一个 struct），消除当前 `inspect.signature` hack。

**备选**: 三参数固定签名 — 放弃，签名刚性，扩展字段需改签名。关键字参数 — 放弃，Python 特有语义，Rust 无法映射。

### D4: Manifest 声明 + 文件名 fallback

扩展目录下 `manifest.yaml` 声明 handler 元数据。无 manifest 时退化为文件名即 handler 名（兼容简单脚本）。

```yaml
name: rss-fetcher
version: 0.1.0
depends: [_lib/http_fetch]
handlers:
  - name: fetch-rss
    entry: handler.py
    role: source
    input_type: Any
    output_type: "list[RawItem]"
entity_types:
  - name: rss-source
    display_name: "RSS 源"
    business_id_field: name
    storage_tier: filesystem
    schema: { properties: { name: { type: string }, url: { type: string } } }
```

**理由**: Manifest 提供核心所需的 NodeTypeDescriptor（role、I/O types）用于 DAG 校验，同时声明 entity types 实现自包含安装。Fallback 保持极简扩展的低门槛。

### D5: importlib 加载 handler

核心通过 `importlib.util.spec_from_file_location` 按路径加载 handler 模块，取 `run` 函数。Bootstrap 时将 `extensions/` 加入 `sys.path` 使 `_lib/` 可被 import。

**理由**: 比 `exec()` 规范，支持模块缓存和相对 import。Rust 迁移时 PyO3 `PyModule::import` 是标准路径。

**备选**: `exec()` — 放弃，无模块缓存，不支持相对 import。subprocess — 放弃，进程开销大，简单 handler 不值得。

### D6: Entity type 双层优先级

加载顺序：扩展 manifest 声明 → 用户 `config/` 覆盖。用户配置优先级高于扩展默认。

**理由**: 扩展自包含（安装即可用），用户可按需覆盖（自定义 schema 字段、display_template 等）。

### D7: 扩展声明式建表

扩展在 manifest 的 `storage.tables` 段声明表结构，核心 bootstrap 时根据声明自动 CREATE TABLE。

**理由**: 扩展开发者不需要懂 alembic，核心完全掌控 schema 演化。未来 Rust 核心可直接根据声明建表。

## Risks / Trade-offs

- **全量重组风险** → 一步到位重构，中间态不可运行。缓解：项目无生产用户，开发阶段可接受短期不可用。重组完成后立即跑全量测试验证。
- **import 路径全面变更** → 所有测试和扩展代码需更新 import。缓解：全局搜索替换，无遗漏风险。
- **_lib/ 通过 sys.path 加载** → 非标准 Python 包管理方式。缓解：仅限扩展内部使用，核心和 core-types 仍是标准包。
- **声明式建表表达力有限** → 复杂索引、约束可能无法通过简单 YAML 声明。缓解：初期只支持基础列类型和单列索引，复杂需求后续迭代。
- **Manifest fallback 歧义** → 无 manifest 时文件名即 handler 名，但缺少 role/I/O type 信息。缓解：fallback 模式下 DAG 校验跳过类型检查，仅用于快速原型。
