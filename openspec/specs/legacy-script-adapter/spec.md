---
capabilities:
  - cap.core.legacy-script-adapter
---
# legacy-script-adapter Specification

## Purpose
定义 LegacyScriptAdapter 通用脚本适配、调用环境隔离、参数提取和 Extension manifest 注册。
## Requirements
### Requirement: 通用脚本适配

LegacyScriptAdapter SHALL 作为一个通用 handler 注册在 Extension manifest 中，能够桥接任意 Python 脚本的函数调用。adapter 从节点 config 读取 `module_path` 和 `function` 字段，运行时 `importlib.import_module` 加载并调用。

#### Scenario: 正常调用外部脚本
- **WHEN** 节点 config 为 `{module_path: "fetch_basic", function: "main"}` 且 HandlerContext.input 包含 ticker
- **THEN** adapter MUST import `fetch_basic` 模块并调用 `fetch_basic.main(ticker)`，将返回值包装为 `NodeOutput(ok=True, payload=result)`

#### Scenario: 脚本抛异常
- **WHEN** 被调用的脚本函数抛出任意异常
- **THEN** adapter MUST catch 异常并返回 `NodeOutput(ok=True, payload=DimResult.error_result(...))`，不向 DagRunner 抛出

### Requirement: sys.path 和 cwd 设置

adapter 在调用脚本前 SHALL 将脚本所在目录加入 `sys.path` 并设置 `os.chdir`，确保脚本内部的相对 import 和文件路径正常工作。调用完成后 MUST 恢复原始 path 和 cwd。

#### Scenario: 脚本依赖相对 import
- **WHEN** `fetch_basic.py` 内部 `from lib.market_router import parse_ticker`
- **THEN** adapter 设置的 sys.path MUST 使该 import 成功

#### Scenario: 调用后恢复环境
- **WHEN** adapter 完成一次脚本调用
- **THEN** sys.path 和 os.getcwd() MUST 恢复到调用前状态

### Requirement: 参数提取

adapter SHALL 支持从 HandlerContext 提取调用参数。参数映射规则通过节点 config 的 `args_map` 字段声明，支持从 `input.payload`（fan-in map）或 `params`（initial_payload）中提取值。

#### Scenario: 从 initial_payload 提取 ticker
- **WHEN** 节点为起始节点，config 声明 `args_map: [{source: "params.ticker"}]`
- **THEN** adapter MUST 将 `HandlerContext.params["ticker"]` 作为第一个参数传入脚本函数

#### Scenario: 从上游 output 提取 industry
- **WHEN** 节点为 Wave 3 fetcher，config 声明 `args_map: [{source: "input.0_basic.data.industry", default: "综合"}]`
- **THEN** adapter MUST 从 fan-in input 中提取 `0_basic` 节点 output 的 `data.industry` 字段，缺失时用默认值 "综合"

### Requirement: Extension manifest 注册

LegacyScriptAdapter MUST 通过 `extensions/uzi-skill/manifest.yaml` 注册为 handler，handler name 为 `legacy-script-adapter`，供多个业务 node type 通过 `handler` 字段复用。DAG 实例的 `type` MUST 引用具体业务 node type，不得直接使用 `legacy-script-adapter` 作为实例类型。

#### Scenario: manifest 加载
- **WHEN** 系统 bootstrap 扫描 `extensions/uzi-skill/manifest.yaml`
- **THEN** HandlerRegistry MUST 包含 `legacy-script-adapter` 条目

#### Scenario: 业务 node type 复用 handler
- **WHEN** UZI-Skill DAG 声明 `0_basic`、`score_dimensions` 或 renderer 实例
- **THEN** 实例 `type` MUST 分别引用具体 `uzi-*` node type，且这些 node type 的 `handler` 均为 `legacy-script-adapter`
