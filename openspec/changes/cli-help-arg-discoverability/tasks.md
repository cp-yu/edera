### Task 1: P0/P0-sub — `add_parser()` 补齐 `help=`

**Goal**: 修复 `cli_help.py` 中缺少的 subcommand 条目，并在 `cli.py` 中所有嵌套 `add_parser()` 调用处补齐 `help=` kwarg，消除 help 链断裂。

**Files**:
- Modify: `packages/core/src/edera_core/cli_help.py`
- Modify: `packages/core/src/edera_core/cli.py`

**Requirements**:
- `cli_help.py` 中 `COMMANDS["dag"].subcommands` 增加 `"add-node"`、`"add-edge"`、`"remove-edge"` 三个条目
- `_dag_parser` 中 `edit_sub.add_parser(...)` 传入 `help=sub["..."]`
- `_entity_type_parser` 中 `materialize_sub.add_parser(...)` 传入 `help=`
- `_config_parser` 中 `system_sub.add_parser(...)` 和 `entity_type_sub.add_parser(...)` 传入 `help=`
- `_query_parser` 中 `briefing_sub`、`advice_sub`、`results_sub` 的 `add_parser(...)` 传入 `help=`

#### Checks

- [ ] C1 P0 `dag edit` 叶子子命令 `--help` 不中断
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "三级子命令 help 不中断"
  - Command: `edera dag edit --help 2>&1`
  - Expect: 输出中包含 `add-node`、`add-edge`、`remove-edge` 及其一行说明

- [ ] C2 P0-sub 三级子命令 `--help` 不中断
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "三级子命令 help 不中断"
  - Command: `for cmd in "entity-type materialize plan" "config system show" "config entity-type list" "query briefing latest" "query advice list" "query results summary"; do edera $cmd --help 2>&1 | head -3; done`
  - Expect: 每个命令输出自身的 usage 与参数，不回退到父级

### Task 2: P1 — 所有 `add_argument()` 补齐 `help=`

**Goal**: 为 `cli.py` 中所有 `add_argument()` 调用补齐 `help=` 文本，含共享 helper 函数和各 parser 函数。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`

**Requirements**:
- 共享 helper（`_watch_arguments`、`_tail_arguments`、`_offset_argument`、`_local_page_arguments`、`_time_range_arguments`）中所有 `add_argument()` 补 `help=`
- entity/relation/entity-type/node/node-type/skill parser 中所有 `add_argument()` 补 `help=`
- dag/event/system/client/config parser 中所有 `add_argument()` 补 `help=`
- query/source/handler/extension parser 及 `main()` 中所有 `add_argument()` 补 `help=`
- 格式标注：JSON 参数标注 `"JSON object"` / `"JSON string"`，复合 ID 标注 `"<dag>.<alias>"`，过滤参数标注 `"key=value"`，有限可选值列出所有选项及默认值

#### Checks

- [ ] C3 二级子命令参数 `help=` 可见
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "二级子命令 help 包含参数说明"
  - Command: `edera entity update --help 2>&1`
  - Expect: `ref`、`--field`、`--value`、`--attributes` 各有 `help=` 文本

- [ ] C4 JSON 参数格式标注
  - Verifies: `specs/edera-cli/spec.md` / Requirement "参数帮助文本格式标注" / Scenario "JSON 参数标注格式"
  - Command: `edera entity create --help 2>&1`
  - Expect: `--attributes` 的 help 文本包含 `JSON object`

- [ ] C5 复合 ID 参数格式标注
  - Verifies: `specs/edera-cli/spec.md` / Requirement "参数帮助文本格式标注" / Scenario "复合 ID 参数标注格式"
  - Command: `edera node status --help 2>&1`
  - Expect: `node_id` 的 help 文本包含 `<dag>.<alias>`

- [ ] C6 有限可选值参数列出选项
  - Verifies: `specs/edera-cli/spec.md` / Requirement "参数帮助文本格式标注" / Scenario "有限可选值参数列出选项"
  - Command: `edera dag retry --help 2>&1`
  - Expect: `--mode` 的 help 文本包含 `single`、`cascade`、`downstream` 及 `default: single`

### Task 3: Subagent 完整性扫描

**Goal**: 通过 subagent 扫描 `cli.py` 源码，确认所有 `add_argument()` 和关键 `add_parser()` 均已包含 `help=`，无遗漏。

**Files**:
- (验证目标) `packages/core/src/edera_core/cli.py`

**Requirements**:
- 所有 `add_argument()` 调用均含 `help=` kwarg（`--version` 除外）
- 所有嵌套 `add_parser()` 调用均含 `help=` kwarg
- 假阳性排除：已有 `help=` 的参数、`action="version"` 参数不重复计算

#### Checks

- [ ] C7 源码扫描无遗漏
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "二级子命令 help 包含参数说明" 与 Scenario "三级子命令 help 不中断"
  - Command: `subagent scout 扫描 cli.py，检查所有 add_argument() 和 add_parser() 的 help= 覆盖率`
  - Expect: subagent 返回 clean pass，无遗漏

### Task 4: Subagent 正确性验证

**Goal**: 通过 subagent 实际调用 `edera <cmd> <sub> --help`，遍历所有 P0/P0-sub 叶子命令和 P1 关键命令，确认 help 输出正确、不中断、格式标注到位。

**Files**:
- (验证目标) `packages/core/src/edera_core/cli.py`

**Requirements**:
- P0/P0-sub 全部 18 处叶子命令 `--help` 输出自身 usage 与参数
- 关键命令（entity create/list/update、dag retry/edit add-node、node status/output、event emit、query briefing show、extension install、source logs）`--help` 输出完整准确
- 无裸参数名（即参数在 usage 中出现但在 help 文本段无说明的行）

#### Checks

- [ ] C8 `--help` 输出全覆盖验证
  - Verifies: `specs/edera-cli/spec.md` / Requirement "CLI Help Surface" / Scenario "二级子命令 help 包含参数说明" 与 Scenario "三级子命令 help 不中断"
  - Command: `subagent 遍历 P0/P0-sub 18 处叶子命令和 P1 关键命令，调用 edera <cmd> <sub> --help，收集输出并判断是否正确`
  - Expect: 所有命令 help 输出正常，无回退、无裸参数
