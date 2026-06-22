## MODIFIED Requirements

### Requirement: CLI Help Surface
`edera` CLI SHALL 在顶层、一级子命令、二级子命令、三级子命令四个层级暴露文档化的 help 文本。所有 `add_argument()` 调用 SHALL 包含 `help=` 文本描述参数用途、格式、类型或默认值。所有 `add_parser()` 调用 SHALL 包含 `help=` 文本，MUST NOT 回退到父级解析器。

#### Scenario: 顶层 help 包含顶层描述与示例
- **WHEN** 用户执行 `edera --help`
- **THEN** 系统 SHALL 输出包含顶层 description、EXAMPLES 段、以及全部 16 个一级子命令的一行说明的 help 文本
- **AND** SHALL 以退出码 0 退出

#### Scenario: 顶层 help 全局选项分组
- **WHEN** 用户执行 `edera --help`
- **THEN** 系统 SHALL 将全局选项 `--identity` 与 `--server` 归入 `Connection` 分组
- **AND** SHALL 将 `--output` 归入 `Output` 分组
- **AND** SHALL 将 `--help` 与 `--version` 归入通用分组

#### Scenario: 一级子命令 help 包含描述与示例
- **WHEN** 用户执行 `edera <command> --help`（其中 `<command>` 为 16 个一级子命令之一，包括 `handler-validate`）
- **THEN** 系统 SHALL 输出该子命令的 description、EXAMPLES 段、以及该子命令全部二级 subcommand 的一行说明
- **AND** SHALL 以退出码 0 退出

#### Scenario: 二级子命令 help 包含参数说明
- **WHEN** 用户执行 `edera <command> <subcommand> --help`（如 `edera entity get --help`）
- **THEN** 系统 SHALL 输出该 subcommand 的 usage 与全部参数的 `help=` 文本
- **AND** SHALL 以退出码 0 退出

#### Scenario: 三级子命令 help 不中断
- **WHEN** 用户执行 `edera <command> <subcommand> <leaf> --help`（如 `edera dag edit default add-node --help`）
- **THEN** 系统 SHALL 输出该叶子命令自身的 usage 与全部参数的 `help=` 文本
- **AND** MUST NOT 回退到父级 `add_parser()` 的 help 输出

#### Scenario: handler-validate help
- **WHEN** 用户执行 `edera handler-validate --help`
- **THEN** 系统 SHALL 输出 `handler-validate` 的 description 与 EXAMPLES 段，与其它一级子命令保持一致的 help 结构
- **AND** SHALL 以退出码 0 退出

## ADDED Requirements

### Requirement: 参数帮助文本格式标注
`help=` 文本 SHALL 对以下参数类型包含格式标注：
- JSON 值参数（如 `--attributes`、`--config`、`--payload-json`）SHALL 标注 `"JSON object"` 或 `"JSON string"`
- 复合标识参数（`node_id`）SHALL 标注 `"<dag>.<alias>"` 格式
- 过滤器参数（`--filter`）SHALL 标注 `"key=value"` 格式
- 具有有限可选值的参数（如 `--mode`）SHALL 在 `help=` 中列出所有可选值和默认值（如 `"Retry strategy: single, cascade, or downstream (default: single)."`）
- 位置参数 SHALL 包含类型或格式说明

#### Scenario: JSON 参数标注格式
- **WHEN** 用户执行 `edera entity create --help`
- **THEN** `--attributes` 的 `help=` 文本 SHALL 包含 `JSON object`

#### Scenario: 复合 ID 参数标注格式
- **WHEN** 用户执行 `edera node status --help`
- **THEN** `node_id` 的 `help=` 文本 SHALL 包含 `<dag>.<alias>` 格式说明

#### Scenario: 有限可选值参数列出选项
- **WHEN** 用户执行 `edera dag retry --help`
- **THEN** `--mode` 的 `help=` 文本 SHALL 列出所有可选值及默认值
