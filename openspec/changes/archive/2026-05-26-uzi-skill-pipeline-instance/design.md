## Context

UZI-Skill 是一个开源股票深度分析工具，其 pipeline 架构（v3.0.0）包含 22 个数据 fetcher、scoring 链和 21 个 renderer。本 change 将其行为建模为本系统 DAG 引擎的一个实例配置，通过 Extension manifest 注册，通过 LegacyScriptAdapter 桥接外部 Python 脚本。

依赖前置 change `dag-resource-semaphore` 提供的 resource semaphore 能力。

关键拓扑特征：
- Wave 1：`0_basic`（串行，所有后续节点的基础）
- Wave 2：18 个非依赖 fetcher（并行，其中 3 个声明 `resource: "v8_isolate"`）
- Wave 3：4 个依赖 `0_basic.industry` 的 fetcher（required 边）
- Score 链：`autofill_mx` + `autofill_playwright`（可并行）→ `score_dimensions` → `generate_panel` → `generate_synthesis`
- Render：21 个 renderer（并行）→ `assemble_report`

## Goals / Non-Goals

**Goals:**
- 完整的 DAG YAML 配置，声明所有节点、边、optional 属性和 resource 引用
- LegacyScriptAdapter 通用实现，支持 `importlib.import_module` + 函数调用
- Extension manifest 注册 adapter handler
- 可通过 `POST /api/pipeline/dag/uzi-skill-analysis/run` 触发，payload 传入 ticker

**Non-Goals:**
- 重写 UZI-Skill 的 fetcher 脚本（保持原样引用，按需微调）
- UZI-Skill 的 legacy fallback 路径（中文名解析、ETF 引导等由 preflight 节点处理）
- 报告的 UI 展示集成（产出 HTML 文件路径即可）

## Decisions

1. **LegacyScriptAdapter 是通用 handler**：不为每个 fetcher 写 wrapper。adapter 读取节点 config 中的 `module_path` 和 `function`，运行时 import 并调用。返回值包装为 `NodeOutput`。

2. **DimResult → NodeOutput 映射**：fetcher 返回的 DimResult 直接作为 `NodeOutput.payload`。quality=ERROR 时 `NodeOutput.ok = True`（业务错误不是调度错误）。节点声明 `optional: true` 作为额外保险。

3. **ticker 通过 initial_payload 传入**：DAG 的 `initial_payload = {"ticker": "300470.SZ"}`，所有无上游的节点（preflight）从 payload 取 ticker。后续节点通过 fan-in input 获取上游 output。

4. **Score 节点的 fan-in**：`score_dimensions` 声明 `fan_in_mode: "barrier"`，depends_on 所有 22 个 fetcher。input 为 `{fetcher_id: DimResult}` map，score 节点内部组装 raw_data dict。

5. **Renderer 节点的 fan-in**：每个 renderer depends_on `generate_synthesis`（获取完整 scored data），`assemble_report` depends_on 所有 21 个 renderer。

## Risks / Trade-offs

- **脚本兼容性**：UZI-Skill 脚本有自己的 sys.path 和依赖假设，adapter 需要在调用前设置正确的 working directory 和 path。可能需要逐个调试。
- **性能**：22 个 fetcher 无并发限制（除 v8_isolate 的 3 个），网络 I/O 密集，实际并发度取决于系统资源和目标 API 的 rate limit。
- **错误粒度**：所有 fetcher 错误都封装在 DimResult 里，调度层只看到"成功"。需要通过 NodeOutput.payload 的 quality 字段做运维可观测性。
