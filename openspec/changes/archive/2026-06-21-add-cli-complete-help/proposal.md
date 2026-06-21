<!--
Smart Routing 决策记录：
- 输入：用户要求「cli 需要有完整的 help」
- 输入长度：> 100 字符
- Design Summary 存在：是（/opsx:explore 已产出，确认 argparse + cli_help.py 路径）
- 多子系统检测：否（单一子系统 CLI help surface）
- 决策：使用 Design Summary，跳过 explore，直接生成制品
-->

## Why

`edera` CLI 是 agent 与人类访问 Edera 控制面的统一入口，但当前 `--help` 在所有层级都只输出 argparse 自动生成的 usage，缺少 description、epilog、参数说明和 EXAMPLES。新用户无法通过 `edera --help` 一眼看清 16 个一级子命令各自的职责，也无法通过 `edera entity --help` 看到 entity 的二级 subcommand 一行说明与典型用法。help 文本是面向外部发布的可观测行为，应当被 spec 显式约束。

## What Changes

- 新增 `packages/core/src/edera_core/cli_help.py`：集中存放顶层 description/epilog、16 个一级子命令的 `CommandHelp` 元信息（description / epilog / subcommands 一行说明）。
- 重构 `packages/core/src/edera_core/cli.py`：顶层 parser 注入 `description / epilog / formatter_class=RawDescriptionHelpFormatter`；全局选项按 `Connection / Output / Common` 分组；每个 `add_parser` 调用从 `cli_help.COMMANDS` 取 `help=`、`description=`、`epilog=`；二级 `add_parser` 同步补充 `help=`。
- 修复 `openspec/specs/edera-cli/spec.md` 中 `Scenario: CLI 可执行` 的子命令枚举（由 15 个补齐为 16 个，加入 `handler-validate`）。
- 新增 `openspec/specs/edera-cli/spec.md` 中关于 `edera --help`、`edera <command> --help`、`edera <command> <subcommand> --help` 输出契约的 Requirements。
- 新增 `packages/core/tests/test_cli_help.py`：对三层 help 输出做内容与退出码断言。

非目标：
- 不引入 Typer/click/Rich，继续使用 argparse。
- 不修改 `--version` 的数据源（仍写死 `0.1.0`）。
- 不修改 `edera-server` / `edera-web` 的 help 行为（独立 scope）。
- 不引入 YAML/JSON 形式的命令元数据目录。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `edera-cli`: 新增 `Requirement: CLI Help Surface`，要求三层 help 输出包含 description、EXAMPLES、二级 subcommand 一行说明；修复 `Scenario: CLI 可执行` 中子命令枚举缺失 `handler-validate` 的一致性问题。

## Impact

- **代码**：`packages/core/src/edera_core/cli.py`（重构）、`packages/core/src/edera_core/cli_help.py`（新增）。
- **测试**：新增 `packages/core/tests/test_cli_help.py`；现有 `test_cli_entity.py / test_cli_skill.py / test_cli_relation_aliases.py` 行为不变，应继续通过。
- **Spec**：`openspec/specs/edera-cli/spec.md` 增补 Requirements + 修复枚举。
- **OPSX**：`cap.core.edera-cli` 的 intent 追加 "exposes a documented help surface at every nesting level"；不新增节点。
- **依赖**：无新增第三方依赖。
- **兼容性**：无 BREAKING；所有现有子命令、flag、env 变量语义保持不变，仅扩展 help 文本。
