# terminology-glossary Specification

## Purpose
此规约记录变更 terminology-unification 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 术语表文档
项目根目录 SHALL 包含 `GLOSSARY.md` 文件，定义所有核心概念的 canonical term、同义词（禁用）、说明和使用约定。

#### Scenario: 核心概念定义
- **WHEN** 开发者查阅 `GLOSSARY.md`
- **THEN** 文档 SHALL 包含以下核心概念的定义：DAG、Node、Edge、Run、run_id、Trigger Entity、TriggerExecutor、Emit、Source

#### Scenario: 禁用同义词标注
- **WHEN** 开发者查阅 `GLOSSARY.md` 中的 DAG 条目
- **THEN** 文档 SHALL 明确标注 `~~Pipeline~~` 为禁用同义词

#### Scenario: 动词约定
- **WHEN** 开发者查阅 `GLOSSARY.md`
- **THEN** 文档 SHALL 包含动词约定表，定义"手动运行 DAG"、"注入事件"、"停止 DAG"等用户意图对应的 API/CLI 命令

### Requirement: 存储层术语约定
`GLOSSARY.md` SHALL 定义数据库表命名约定和字段命名规范。

#### Scenario: 表命名规范
- **WHEN** 开发者查阅 `GLOSSARY.md` 存储层部分
- **THEN** 文档 SHALL 列出所有表名（`dag_runs`、`node_runs`、`node_outputs`、`edge_inputs`、`emit_records`、`event_group_bits`）及其说明

#### Scenario: dag_runs.source 字段约定
- **WHEN** 开发者查阅 `GLOSSARY.md` 字段约定部分
- **THEN** 文档 SHALL 定义 `dag_runs.source` 列的合法值格式：`manual`、`startup`、`retry`、`trigger:<trigger_name>`

### Requirement: Sub-DAG 关系约定
`GLOSSARY.md` SHALL 定义 sub-DAG 的 run_id 独立性和父子关系字段。

#### Scenario: Sub-DAG run_id 独立性
- **WHEN** 开发者查阅 `GLOSSARY.md` Sub-DAG 部分
- **THEN** 文档 SHALL 说明子 DAG 有独立的 `run_id`，通过 `node_runs.metadata.parent_run_id` 关联父 run

### Requirement: 术语一致性检查
项目 SHALL 在 CI 中添加术语一致性检查，禁止新代码引入已废弃术语。

#### Scenario: 禁止 pipeline_runs 表名
- **WHEN** 开发者提交包含 `pipeline_runs` 字符串的代码
- **THEN** CI SHALL 失败并提示使用 `dag_runs`

#### Scenario: 禁止 cycle_id 变量名
- **WHEN** 开发者提交包含 `cycle_id` 变量名的代码
- **THEN** CI SHALL 失败并提示使用 `run_id`

