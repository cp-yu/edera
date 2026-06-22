## Why

`edera` CLI 的二、三级子命令 `--help` 输出中，大量参数缺少 `help=` 文本，用户无法从 help 中判断参数用途、格式或可选值。`dag edit add-node` / `add-edge` / `remove-edge` 三个叶子命令的 `add_parser()` 未传入 `help=`，导致 `--help` 回退到父级 `dag edit` 的 help，参数完全不可见。这直接违反了 spec `cap.core.edera-cli` 中「二级子命令 help 包含参数说明」的要求。

## What Changes

- 补全 `cli.py` 中所有 `add_argument()` 调用的 `help=` 参数（125 处），含共享 helper 函数 `_watch_arguments`、`_tail_arguments`、`_offset_argument`、`_local_page_arguments`、`_time_range_arguments`
- 补全 18 处嵌套 `add_parser()` 调用的 `help=`，修复 help 链断裂，涉及 `_dag_parser`（P0）、`_entity_type_parser`、`_config_parser`、`_query_parser`（P0-sub）
- `cli_help.py` 中 `dag.subcommands` 增加 `add-node`、`add-edge`、`remove-edge` 三个条目
- 对格式敏感参数标注元语法：JSON 参数标注 `"JSON object"`，复合 ID 标注 `"<dag>.<alias>"`，过滤器标注 `"key=value"`

## Capabilities

### Modified Capabilities
- `cap.core.edera-cli`: 强化「CLI Help Surface」requirement——所有 `add_argument()` 必须含 `help=`，所有 `add_parser()`（含三级嵌套）必须含 `help=`，参数说明中须标注 JSON 格式、choices 和复合 ID 格式

## Impact

- 仅修改 `packages/core/src/edera_core/cli.py` 和 `packages/core/src/edera_core/cli_help.py`
- 无行为变更，不影响 gRPC 协议、数据模型或其他组件
- 参数签名不变，不涉及 **BREAKING** 变更
