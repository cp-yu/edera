### Task 1: 创建 cli_help 模块骨架

**Goal**: 新增 `cli_help.py`，定义 `CommandHelp` dataclass、`COMMANDS` 字典、顶层 `TOP_DESCRIPTION` 与 `TOP_EPILOG`。

**Files**:
- Create: `packages/core/src/edera_core/cli_help.py`

**Requirements**:
- 定义 frozen dataclass `CommandHelp`，字段 `description / help_line / epilog / subcommands`
- 提供 `TOP_DESCRIPTION` 与 `TOP_EPILOG`（含 EXAMPLES 段与 ENV 说明）
- 提供 `_fmt_epilog` 工具函数，统一多行 epilog 缩进
- 提供 `COMMANDS: dict[str, CommandHelp]`，覆盖全部 16 个一级子命令键

#### Checks

- [x] C1 Verify cli_help 模块可导入
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "顶层 help 包含顶层描述与示例"
  - Command: `.venv/bin/python -c "from edera_core import cli_help; assert cli_help.TOP_DESCRIPTION and cli_help.TOP_EPILOG and len(cli_help.COMMANDS) == 16"`
  - Expect: 命令退出码 0，断言通过

### Task 2: 填充 16 个一级子命令的 CommandHelp 文案

**Goal**: 为 entity / relation / entity-type / node / node-type / skill / dag / event / system / client / config / query / source / handler / extension / handler-validate 各写入 description、help_line、epilog、二级 subcommands 一行说明。

**Files**:
- Modify: `packages/core/src/edera_core/cli_help.py`

**Requirements**:
- 每个一级子命令的 `help_line` 与 `description` 以英文为主，关键中文短语括注
- 每个一级子命令的 `epilog` 至少含一条 EXAMPLES 用例（命令保留纯英文）
- `subcommands` 字典覆盖该一级子命令下全部二级 subcommand 名（与 `cli.py` 中 `add_parser` 调用一一对应）

#### Checks

- [x] C2 Verify 全部一级子命令文案完整
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "一级子命令 help 包含描述与示例"
  - Command: `.venv/bin/python -c "from edera_core.cli_help import COMMANDS; [assert v.description and v.help_line and v.epilog for v in COMMANDS.values()]"`
  - Expect: 命令退出码 0，无 AssertionError

### Task 3: cli.py 顶层 parser 注入 description / epilog / formatter_class / 选项分组

**Goal**: 重构 `main()`，给顶层 `ArgumentParser` 注入 `description`、`epilog`、`formatter_class=RawDescriptionHelpFormatter`，并将 `--identity / --server` 归入 Connection 组，`--output` 归入 Output 组，`--help / --version` 归入 Common 组。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`

**Requirements**:
- 顶层 parser `description=cli_help.TOP_DESCRIPTION`、`epilog=cli_help.TOP_EPILOG`、`formatter_class=RawDescriptionHelpFormatter`
- 全局选项按 Connection / Output / Common 三组归类
- 不改变任何现有 flag 名、默认值、env 变量语义

#### Checks

- [x] C3 Verify 顶层 help 含 description 与 EXAMPLES
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "顶层 help 包含顶层描述与示例"
  - Command: `.venv/bin/edera --help`
  - Expect: 退出码 0，stdout 含 TOP_DESCRIPTION 关键短语与 `EXAMPLES` 段标识
- [x] C4 Verify 顶层 help 选项分组
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "顶层 help 全局选项分组"
  - Command: `.venv/bin/edera --help`
  - Expect: stdout 含 `Connection:`、`Output:` 分组标题

### Task 4: cli.py 一级与二级 subparsers 接入 cli_help 文案

**Goal**: 把 16 个一级 `subparsers.add_parser(name)` 调用改造为传入 `help / description / epilog / formatter_class`，二级 `add_parser` 调用从 `cli_help.COMMANDS[name].subcommands` 取 `help=`。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`

**Requirements**:
- 每个 `add_parser(name, ...)` 的 `help=` 取自 `cli_help.COMMANDS[name].help_line`
- 每个 `add_parser(name, ...)` 的 `description=`、`epilog=`、`formatter_class=RawDescriptionHelpFormatter` 取自 `cli_help.COMMANDS[name]`
- 二级 `add_parser(subname, ...)` 的 `help=` 取自 `cli_help.COMMANDS[parent].subcommands[subname]`
- `handler-validate` 一级子命令单独处理（无二级 subparser），同样注入 description/epilog

#### Checks

- [x] C5 Verify 一级子命令 help 含 description 与 EXAMPLES
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "一级子命令 help 包含描述与示例"
  - Command: `.venv/bin/edera entity --help`
  - Expect: 退出码 0，stdout 含 entity description 关键短语与 `EXAMPLES` 段
- [x] C6 Verify handler-validate help
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "handler-validate help"
  - Command: `.venv/bin/edera handler-validate --help`
  - Expect: 退出码 0，stdout 含 handler-validate description 与 EXAMPLES 段
- [x] C7 Verify 二级子命令 help 含参数说明
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "二级子命令 help 包含参数说明"
  - Command: `.venv/bin/edera entity get --help`
  - Expect: 退出码 0，stdout 含 `usage:` 与 `ref` 位置参数说明

### Task 5: 新增 test_cli_help.py 覆盖三层 help

**Goal**: 新增测试断言三层 help 的退出码与关键子串。

**Files**:
- Test: `packages/core/tests/test_cli_help.py`

**Requirements**:
- 顶层 help 测试：`edera --help` 退出码 0，含顶层 description、16 个一级子命令名、EXAMPLES 标识
- 一级子命令 help 测试：抽样 entity/dag/client 三个子命令，断言 description 与 EXAMPLES
- 二级子命令 help 测试：抽样 `edera entity get --help`，断言 usage 与参数说明

#### Checks

- [x] C8 Verify 测试套件通过
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "顶层 help 包含顶层描述与示例"
  - Command: `.venv/bin/pytest packages/core/tests/test_cli_help.py -v`
  - Expect: 全部用例通过
- [x] C9 Preserve 现有 CLI 行为不破坏
  - Preserves: `openspec/specs/edera-cli/spec.md` / Requirement "身份声明" / Scenario "环境变量身份"
  - Command: `.venv/bin/pytest packages/core/tests/test_cli_entity.py packages/core/tests/test_cli_skill.py packages/core/tests/test_cli_relation_aliases.py`
  - Expect: 现有测试全部通过，验证未引入行为回归
