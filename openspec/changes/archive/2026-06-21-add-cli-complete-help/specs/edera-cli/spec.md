## MODIFIED Requirements

### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。

#### Scenario: CLI 可执行
- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、relation、entity-type、node、node-type、skill、dag、event、system、client、config、query、source、handler、extension、handler-validate）

#### Scenario: 版本查询
- **WHEN** 用户执行 `edera --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Console scripts 集合
- **WHEN** 检查包的 console scripts
- **THEN** 系统 SHALL 注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`

## ADDED Requirements

### Requirement: CLI Help Surface
`edera` CLI SHALL 在三个层级（顶层、一级子命令、二级子命令）暴露文档化的 help 文本，使用户无需查阅外部文档即可理解命令用途与典型用法。

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
- **THEN** 系统 SHALL 输出该 subcommand 的 usage 与全部参数的 help 文本
- **AND** SHALL 以退出码 0 退出

#### Scenario: handler-validate help
- **WHEN** 用户执行 `edera handler-validate --help`
- **THEN** 系统 SHALL 输出 `handler-validate` 的 description 与 EXAMPLES 段，与其它一级子命令保持一致的 help 结构
- **AND** SHALL 以退出码 0 退出
