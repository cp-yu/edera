## Context

`edera` CLI 入口位于 `packages/core/src/edera_core/cli.py`（1608 行单文件），由顶层 `ArgumentParser(prog="edera")` 与 16 个一级子命令、~94 个二级/三级子命令构成。当前全文件：

- `help=` 使用 0 次
- `description=` 使用 0 次
- `epilog=` 使用 0 次
- `formatter_class=` 使用 0 次

因此 `edera --help` 仅输出 argparse 自动生成的 usage 行与裸子命令枚举；`edera entity --help` 仅列出二级 subcommand 名字，无任何说明。`openspec/specs/edera-cli/spec.md` 已经规定了 16 个一级子命令的行为契约，但 `Scenario: CLI 可执行` 仅枚举了 15 个（漏掉 `handler-validate`），且没有对 help 文本内容提出任何 Requirement。

约束（来自全局 CLAUDE.md）：精简高效、毫无冗余；非必要不形成注释/抽象；YAGNI；surgical changes；以项目代码为判断依据。

## Goals / Non-Goals

**Goals:**

- 三层 help（顶层 / 一级子命令 / 二级子命令）均含 description、EXAMPLES、二级 subcommand 一行说明。
- 文案与挂载逻辑解耦：`cli.py` 仅负责挂载，`cli_help.py` 集中文案。
- 文案以英文为主，关键中文短语括注（如 `entity — Manage entities (实体管理)`），与项目 spec 中文风格兼容。
- 通过 spec 显式约束 help 输出契约，使其成为可观测行为。
- 顺手修复 spec 中 15/16 子命令枚举不一致问题。

**Non-Goals:**

- 不引入 Typer / click / Rich（避免新依赖；保持 argparse）。
- 不修改 `--version` 数据源。
- 不修改 `edera-server` / `edera-web` 的 help 行为。
- 不引入 YAML/JSON 命令元数据目录。
- 不重写 `_exit_error` 或改变错误退出语义。

## Decisions

### Decision 1: 维持 argparse，不迁移到 Typer/click

**Rationale**: 项目仍处开发期无历史负担（项目 CLAUDE.md 明示），但当前 CLI 已有 110 个 `add_parser` 调用与完整的 dispatch 逻辑。迁移到 Typer 需要重写所有 subcommand 注册、改变错误退出码语义、并新增运行时依赖，违反 surgical changes 与 YAGNI 原则。argparse 通过 `description / epilog / formatter_class / help=` 已能满足「对外发布质量」help 的全部需求。

**Alternatives considered**:
- Typer + Rich：自动补全、彩色、动态宽度更好，但代价是依赖膨胀与大范围重写。
- click：与 Typer 类似，且与 typing 集成弱于 Typer。

### Decision 2: 拆出 `cli_help.py`，文案与挂载分离

**Rationale**: 若把所有 `description / epilog / help` 字符串内联到 `cli.py` 的 110 个 `add_parser` 调用里，文件将从 1608 行膨胀至 ~2200 行，且文案与逻辑混杂难以审阅。拆出 `cli_help.py` 后，`cli.py` 保持精简（仅挂载），文案集中可被 doc 工具与测试单独引用。

**结构**:

```python
# cli_help.py
@dataclass(frozen=True)
class CommandHelp:
    description: str        # 子命令 --help 顶部多行描述
    help_line: str          # 出现在顶层 --help 的一行说明
    epilog: str             # EXAMPLES 段
    subcommands: dict[str, str]  # 二级 subcommand → 一行 help

COMMANDS: dict[str, CommandHelp] = {
    "entity": CommandHelp(...),
    ...
    "handler-validate": CommandHelp(...),
}

TOP_DESCRIPTION = "..."
TOP_EPILOG = "..."  # 含 EXAMPLES + ENV 说明
```

**Alternatives considered**:
- 内联 kwargs：见上，文件膨胀。
- YAML/JSON 目录：需自写 schema、加载层、dict→kwarg 转换；类型安全弱于 dataclass；过早抽象。

### Decision 3: 使用 `RawDescriptionHelpFormatter`

**Rationale**: 默认 `HelpFormatter` 会把 description 与 epilog 中的换行折叠为单行，破坏 EXAMPLES 的多行结构。`RawDescriptionHelpFormatter` 仅保留 description/epilog 原始格式，对 argument help 仍做正常 wrap，平衡可读性与结构保留。

### Decision 4: 顶层全局选项分组为 `Connection / Output / Common`

**Rationale**: 当前 `--identity / --server / --output / --version` 平铺在 `options:` 段，新用户无法区分连接相关与输出相关。使用 `parser.add_argument_group("Connection")` 等三个组即可让 `edera --help` 一眼区分语义，仅 3 行额外代码。

### Decision 5: 双语文案策略 — 英文为主 + 中文括注

**Rationale**: argparse 默认风格为英文，纯中文会与 usage 行、`-h, --help` 等自动生成段落冲突，观感不统一；纯英文又与项目 spec 的中文风格脱节。折中：description 与 help_line 以英文起头，关键术语括注中文（如 `entity — Manage entities (实体管理)`）。EXAMPLES 与 usage 行保持纯英文（命令本身即英文）。行宽超过 ruff `line-length = 100` 时只保留英文。

### Decision 6: spec 修复 `handler-validate` 枚举一致性

**Rationale**: `Scenario: CLI 可执行` 列举 15 个一级子命令，但代码实际注册 16 个（`handler-validate` 单独走 `Requirement: Handler 子命令` 路径）。此为既有 spec 与实现不一致，顺手在补 help 文本的同时修复，避免新增 help Requirement 时再次漏列。

## Risks / Trade-offs

- **[文案工作量集中]** 16 × (1 description + 1 epilog + 平均 ~6 个 subcommand help) ≈ 130 条文案 → 通过 `cli_help.py` 一次性铺开，不污染主逻辑；review 时只看一个文件。
- **[`RawDescriptionHelpFormatter` 缩进敏感]** epilog 中的多行字符串需手动对齐 → 在 `cli_help.py` 内提供 `_fmt_epilog` 工具统一处理缩进与换行。
- **[双语括注可能超长]** 部分英文 + 中文括注组合会超过 100 字符 → 超长时只保留英文，不破坏 ruff。
- **[行为未变但测试覆盖薄]** 现有 `test_cli_*.py` 不校验 help 内容 → 新增 `test_cli_help.py` 专门覆盖三层 help 的退出码与关键子串；用 `subprocess` 或 `parser.parse_args(["--help"])` 触发后捕获 stdout。
- **[spec 行为扩张]** 新增 `Requirement: CLI Help Surface` 会增加 spec 维护成本 → Requirement 仅约束「description/EXAMPLES/二级 subcommand help 存在」，不约束具体文案措辞，避免文案微调即打破 spec。

## Migration Plan

开发期无历史负担，无需分阶段迁移。

1. 新增 `cli_help.py`，写入顶层文案 + 16 个 `CommandHelp`。
2. 重构 `cli.py`：顶层 parser 注入文案 + 分组 + formatter；逐个 `add_parser` 替换为从 `cli_help.COMMANDS` 取值；二级 `add_parser` 补 `help=`。
3. 跑 `pytest packages/core/tests/test_cli_*.py` 确认现有用例不破。
4. 新增 `test_cli_help.py` 覆盖三层 help。
5. 更新 `openspec/specs/edera-cli/spec.md` 增补 Requirements 与修复枚举。

回滚：单 PR 即可整体回滚，无数据/配置迁移。

## Open Questions

无。所有 scope-affecting 问题已在 `/opsx:explore` 阶段确认：

- 子命令数：16（spec 补 `handler-validate`）
- help 语言：英文主 + 中文括注
- 文本存放：拆出 `cli_help.py`
- 范围：一次到位，三层 help 全覆盖
