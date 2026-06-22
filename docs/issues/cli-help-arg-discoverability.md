# CLI Help：参数可发现性与格式提示不足

## 现状

`edera --help` 的顶级 + 一级子命令层 help 质量高（description / examples / epilog 齐全）。但从二级叶子命令开始，参数信息退化严重——大量 `add_argument()` 没有 `help=` 文本，用户只能看到裸参数名，无法从 help 中判断参数用途、格式或可选值。

## 影响

仅凭 `--help` 无法独立完成以下操作：

- 不知道 `--attributes` 期望 JSON 对象
- 不知道 `--filter` 的 key=value 语法
- 不知道 `--nodes` 的格式（逗号分隔？JSON 数组？）
- 不知道 `expression` 查询语法
- 不知道 `--mode` 的可选值（源码默认 `"single"`，但 help 中无提示）
- **`dag edit add-node/remove-edge/add-edge` 三个子命令的 `--help` 完全不显示自身参数**，回退到父级 help

## 受影响命令清单

### P0：help 链断裂（参数完全不可见）

| 命令 | 实际可用参数 | `--help` 显示 |
|------|-------------|--------------|
| `dag edit <dag> add-node` | `--id`, `--alias`, `--type`(required), `--config` | 只显示父级 `dag edit` 的 help |
| `dag edit <dag> add-edge` | `--from`(required), `--to`(required), `--optional` | 同上 |
| `dag edit <dag> remove-edge` | `--from`(required), `--to`(required) | 同上 |

**根因**：`cli.py` 中 `edit_sub.add_parser(...)` 未传入 `help=` / `description=` 等 kwargs，argparse 的 `--help` 回退到父解析器。

### P1：参数存在但无 help 文本

以下参数在 help 中只显示参数名，无任何说明（`help=` 缺失）：

**entity**
- `create`: `--type`, `--id`, `--attributes`
- `list`: `--type`, `--filter`
- `update`: `ref`, `--field`, `--value`, `--attributes`
- `query`: `expression`
- `import`: `path`, `--file`, `--type`
- `export`: `ref`, `--type`

**relation**
- `list`: `--from`, `--to`, `--type`
- `create`: `--metadata`
- `delete`: `id`

**node**
- `status`, `stop`, `resume`: `node_id`（格式 `dag.node-id` 无提示）
- `output`: `output_args`（子命令 `export`/`query` 无提示）
- `logs`: `node_id`, `--run-id`

**node-type**
- `show`, `create`, `save`, `delete`: `name`

**skill**
- `show`, `update`, `export`, `delete`: `name`

**dag**
- `show`, `create`: `dag_name`
- `retry`: `--nodes`, `--mode`, `--source-shared-inputs`, `--node-inputs`, `--append-nodes`

**event**
- `emit`: `event`, `--payload-json`, `--source`, `--depth`

**system**
- `repair-source`: `source_name`

**config**
- `read`: `kind`, `name`
- `save`: `kind`, `name`

**query**
- `briefing show`: `briefing_id`
- `advice show`: `advice_id`
- `results summary`: `--stock-code`, `--direction`, `--created-from`, `--created-to`
- `node-outputs`: `--node-id`, `--run-id`
- `node-history`: `dag_name`, `node_id`

**source**
- `repair-task`: `source_name`

**handler**
- `show`, `save`: `name`

**extension**
- `show`, `install`, `delete`, `reactivate`: `name`
- `import`: `path`
- `export`: `name`
- `import-entities`: `--file`
- `export-entities`: `--entities`, `--name`, `--version`

## 修复方案

### P0：dag edit 子命令

`cli.py` 中 `edit_sub.add_parser("add-node")` 等三处，传入 `help=` kwarg（来自 `cli_help.py` 中新增的 subcommands 条目）。

### P1：补齐 help= 文本

对 `cli.py` 中所有缺少 `help=` 的 `add_argument()` 调用，补充描述。原则：

- **文本精简**，只说明格式/类型/默认值，不重复已可见的信息
- 对 JSON 参数标注 `"JSON object"`
- 对 choices 隐含的参数显式化（如 `--mode` 在 `--help` 中看不到 `single`）
- 对复合参数（如 `node_id`）标注格式 `"<dag-name>.<node-alias>"`
