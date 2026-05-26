## Why

将 UZI-Skill 股票深度分析管道建模为本系统的一个 DAG 实例配置，验证 Entity-driven DAG 引擎消费外部 pipeline 的能力。UZI-Skill 的 22 fetcher + scoring + 21 renderer 是一个典型的宽并行 + 串行链 + fan-in 拓扑，作为引擎的首个非内建实例。

## What Changes

- 新增 Extension：`extensions/uzi-skill/manifest.yaml`，注册 LegacyScriptAdapter handler 和相关 Entity Type
- 新增 DAG 配置：`config/dags/uzi-skill-analysis.yaml`，声明 ~50 节点 + 边 + resource 引用
- 新增 LegacyScriptAdapter：通用 adapter，将 `HandlerContext` 转为 UZI-Skill 脚本的调用约定（`module.main(ticker, ...)`）
- 新增 Resource Entity 实例：`v8_isolate`（permits=1）
- 节点拓扑：preflight → 0_basic → 18 fetcher 并行 → 4 dependent fetcher → autofill(2 并行) → score → panel → synthesis → 21 renderer 并行 → assemble

## Capabilities

### New Capabilities
- `uzi-skill-dag-instance`: UZI-Skill 分析管道的 DAG 实例配置，覆盖节点声明、边拓扑、resource 引用和 fan-in 模式
- `legacy-script-adapter`: 通用 LegacyScriptAdapter handler，将 HandlerContext 转为外部 Python 脚本调用约定

### Modified Capabilities

## Impact

- `extensions/uzi-skill/` — 新增 extension 目录（manifest + adapter 代码）
- `config/dags/uzi-skill-analysis.yaml` — 新增 DAG 定义
- `config/entities.yaml` — 新增 `v8_isolate` Resource Entity
- 依赖 `dag-resource-semaphore` change 提供的 semaphore 能力
