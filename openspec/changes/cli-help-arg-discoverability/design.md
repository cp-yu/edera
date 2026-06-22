## Context

`edera` CLI 当前 help 体系为三层结构：顶层 `_command_kwargs()` 注入 `description`/`help_line`/`epilog`（来源 `cli_help.py`），一级子命令通过 `help=sub["<name>"]` 引用 `COMMANDS[top].subcommands`，但二级及更深的 `add_argument()` 和嵌套 `add_parser()` 大量缺失 `help=`。

`cli.py` 已有 1600+ 行，`cli_help.py` 的 `CommandHelp` 数据类仅含 `description`/`help_line`/`epilog`/`subcommands`（dict → 一行说明），不承载参数级 help。

## Goals / Non-Goals

**Goals:**
- 所有 `add_argument()` 调用（含共享 helper 函数）均有 `help=` 文本
- 所有嵌套 `add_parser()`（含三级子命令）均有 `help=`，help 链不中断
- 参数说明中标注 JSON 格式、choices、复合 ID 格式等元信息
- 不改变现有 `cli_help.py` 数据结构，不改动参数签名或行为

**Non-Goals:**
- 不改动顶层和一级子命令的 help 体系（已完备）
- 不向 `cli_help.py` 扩展参数级 help catalog
- 不产生新的 CLI 行为或 gRPC 协议变更

## Decisions

### D1: 参数级 help 直接 inline 在 `add_argument()` 中

**选择**: 直接在 `cli.py` 中 `add_argument(help="...")` 补齐文本。

**备选**: 在 `cli_help.py` 中扩展 `CommandHelp` 增加 `parameters` 字段。
**拒绝原因**: 引入新的数据结构层增加复杂度，125 处文本跨两个文件查找反而降低可读性。参数 help 与参数定义在同一行更自然。

### D2: P0/P0-sub 嵌套 `add_parser()` 从 `cli_help.py` 取 `help=`

**选择**: 扩展 `COMMANDS[<top>].subcommands` dict，新增叶子子命令条目，`_dag_parser` 等函数中引用 `help=sub["<name>"]`。

**备选**: 直接 inline `help="..."` 而不通过 `cli_help.py`。
**拒绝原因**: 一级子命令已有 `help=sub["<name>"]` 的 pattern，保持一致性。P0/P0-sub 是 `add_parser()` 调用，语义上与一级子命令同级（都是一行说明），适合用 `cli_help.py` 管理。

### D3: help 文本语言约定

- 自然语言用英文，与现有 `help=` 文本和 argparse 惯例一致
- 格式标注用元语法：`"JSON object"`、`"key=value"`、`"<dag>.<alias>"`、`"default: ..."` 等
- choices 隐式参数（如 `--mode`）在 help 中显式列出可选值

### D4: 改动按 parser 函数分组

125 处改动按 `_entity_parser` / `_dag_parser` / ... 分组实施，便于 review 和验证。共享 helper 函数（`_watch_arguments` 等）作为独立组。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| help 文本与实际参数行为不一致 | 全部基于现有代码逻辑撰写，不猜测行为；subagent 验证阶段调用 `--help` 对照 |
| 125 处改动量大会引入 typo | subagent 源码扫描 + 实际调用 `--help` 双验证 |
| help 文本过长导致 argparse 输出阅读体验下降 | 单行 ≤ 80 字，format 标注用反引号，choices 用逗号分隔 |
