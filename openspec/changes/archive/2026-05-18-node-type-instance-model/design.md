## Context

当前节点系统将类型定义（`config/nodes/*.yaml`）和 DAG 中的节点引用混为一体。DAG YAML 的 `nodes` 列表直接使用 type name，前端通过 `addExistingNode()` 做去重检查阻止同名节点重复添加。LLM 和 Function 节点共用 `skills` 字段但语义不同。节点无 role 声明，handle 渲染不区分 source/sink，连线无类型校验。

后端执行已按 DAG 拓扑调度，改为 instance ID 索引的改动面较小。LLM 节点的实际执行由 pi 负责，本程序只管配置定义和结果接收。

## Goals / Non-Goals

**Goals:**
- 建立 NodeType / NodeInstance 分层模型，支持同类型多实例
- 分离 LLM 和 Function 节点的配置语义（skills vs handler）
- 通过 role 声明驱动 handle 可见性和连线校验
- 提供节点管理页面，支持 LLM 类型 UI 创建和 Function 类型代码编辑
- 独立 Skill 注册表，LLM 实例可自由配置 skills

**Non-Goals:**
- 执行沙箱隔离（后续可加 Bubblewrap）
- LLM 节点执行细节（由 pi 负责）
- 结构化类型系统（子类型、泛型推导等）
- 旧格式兼容层

## Decisions

### D1: 实例标识 — UUID + 别名

实例使用 UUID 作为稳定标识，可选 `alias` 字段作为人类可读标签。边引用 UUID，重命名别名不破坏拓扑。

替代方案：自增后缀（`rss-fetcher-1`）— 重命名时需级联更新所有边引用，脆弱。

### D2: Role 显式声明

节点类型 YAML 新增 `role: source | processor | sink`。不从 I/O 签名推导，因为 notifier 的 `output_type` 非空但语义上是 sink。

替代方案：从 `source_names` 存在性和 `output_type` 是否为空推导 — 语义歧义，notifier 会被误判为 processor。

### D3: LLM / Function 字段分离

Function 节点：`skills` 重命名为 `handler`，指向执行入口函数。无 skills 概念。
LLM 节点：保留 `skills` 列表（实例可自由增删），新增 `system_prompt_file` 引用外部 prompt 文件。

替代方案：统一字段名 — 同名不同义造成持续认知混淆。

### D4: 连线校验分层策略

- Function 节点：I/O 类型不匹配时硬阻止连线
- LLM 节点：类型不匹配时允许连线但显示 warning（黄色/虚线）
- Role 约束：source 无输入 handle（不可连入），sink 无输出 handle（不可连出）
- 校验时机：拖拽过程中实时反馈（ReactFlow `isValidConnection`）

替代方案：统一硬阻止 — LLM 本质处理文本，硬限制削弱灵活性。

### D5: 类型匹配规则 — 简单层级

- `Any` 兼容一切输入
- `list[X]` 精确匹配泛型参数
- 其余字符串精确比较

替代方案：结构化类型 AST — 当前类型种类少于 10 个，过度工程。

### D6: 实例级配置范围

实例只能覆盖运行时参数：`source_names`、`parameters`、`model`、`skills`（仅 LLM）。
结构性字段（`input_type`、`output_type`、`role`、`handler`、`system_prompt_file`）锁定在类型层。

替代方案：全部可覆盖 — 实例改 I/O 类型会破坏连线校验基础。

### D7: Skills 配置自由度

LLM 节点类型定义的 skills 列表是默认启用集。实例可以：
- 取消默认 skill
- 追加类型未定义的 skill（从全局 skill 注册表选取）

System prompt 类型锁定，不可实例覆盖 — prompt 定义节点"身份"。

### D8: Skill 注册表

独立目录 `config/skills/`，每个 skill 一个 YAML 文件：
```yaml
name: summarize
description: "对输入文本进行摘要"
handler: summarize       # 指向 skill_handlers/summarize.py
parameters_schema:
  type: object
  properties:
    max_length: { type: integer, default: 500 }
```

Skill handler 放在 `skill_handlers/` 目录，与 function 节点的 `handlers/` 分离。两者调用语境不同（DAG 数据流 vs LLM function calling 参数）。

### D9: Function handler 动态加载

约定目录 `handlers/{handler_name}.py`，暴露标准签名：
```python
def run(input_data: Any, parameters: dict, context: RunContext) -> Any
```
后端通过 `importlib` 动态加载。新增 function 节点 = 一个 py 文件 + 一个 YAML 配置。

### D10: DAG YAML 新格式

```yaml
name: default
nodes:
  - id: "a3f2b1c4"
    type: rss-fetcher
    alias: "crypto-rss"
    config:
      source_names: [sample-rss]
  - id: "b7e9d2a1"
    type: reader
    alias: "news-reader"
    config:
      skills: [summarize]
      model: hf-share/deepseek-v4-flash
edges:
  - from: "a3f2b1c4"
    to: "b7e9d2a1"
    fan_in: false
    fan_out: false
ui:
  nodes:
    "a3f2b1c4": { x: 100, y: 200 }
```

### D11: 节点管理页面

顶级路由 `/nodes`，侧边栏新增导航入口。三个 tab：
- **LLM 节点**：创建/编辑类型（name、role、system_prompt、默认 skills、I/O 类型、默认 model）
- **Function 节点**：创建/编辑类型（name、role、handler 代码、I/O 类型、parameters schema）。内嵌代码编辑器。
- **Skills**：创建/编辑 skill（name、description、handler 代码、parameters_schema）

### D12: Inspector 表单生成 — 混合策略

核心字段（alias、model、skills 多选、source_names）硬编码布局，提供精细 UX。
`parameters` 字段用 JSON Schema 动态生成表单。
选中边时 Inspector 切换为边配置面板（fan_in / fan_out 开关）。

### D13: QuickAddPanel 改造

- 按 role 分组展示（Sources / Processors / Sinks）
- 去掉去重限制，允许同类型多次拖入
- 搜索同时匹配类型名和已有实例别名

### D14: LLM 节点可为任意 role

LLM 节点的 role 由类型定义显式声明，与 `type: llm | function` 正交。LLM source 节点在 DAG 执行时与 function source 统一触发。

## Risks / Trade-offs

- [UUID 可读性] 边引用 UUID 降低 YAML 手动编辑体验 → 通过 alias 和 UI 编辑缓解，手动编辑非主要场景
- [一次性迁移] 旧格式直接废弃，无兼容层 → 当前仅一个 DAG 文件，手动迁移 5 分钟
- [无执行隔离] handler 在主进程执行，崩溃影响调度器 → 本机工具可接受，后续加 Bubblewrap
- [Skill 自由追加] 实例追加类型未定义的 skill 可能产出不兼容数据 → LLM 节点本身有文本兜底能力，且连线已有 warning 提示
- [代码编辑安全] UI 可编辑 handler 代码 → 仅本机访问，用户即管理员

## Migration Plan

1. 重构 `config/nodes/*.yaml` 格式（加 role、分离 handler/skills/system_prompt_file）
2. 创建 `config/skills/`、`handlers/`、`skill_handlers/`、`prompts/` 目录
3. 手动改写 `config/dags/default.yaml` 为新格式
4. 后端适配：节点加载、DAG 解析、运行状态索引改为 instance ID
5. 前端类型重构 → Canvas/Inspector/QuickAddPanel 适配
6. 新增节点管理页面

回滚策略：git revert 整个 change 分支。数据层变更仅涉及 config YAML 文件，可手动恢复。

## Open Questions

- `RunContext` 的具体字段待实现时确定（至少包含 node_id、dag_name、logger）
- Skill handler 的标准签名待确定（参数来自 LLM function calling，与 node handler 不同）
- fan_in 等待策略的超时机制待定义
