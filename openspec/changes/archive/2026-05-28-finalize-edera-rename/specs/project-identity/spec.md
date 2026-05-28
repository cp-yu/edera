## MODIFIED Requirements

### Requirement: Project command and control command
系统 SHALL 提供 `edera`、`edera-server`、`edera-web` 三个 console scripts，分别承担控制 CLI、后端引擎、网页 BFF 入口。系统 MUST NOT 再提供 `stockimformation` 或 `rig` console script。

#### Scenario: Project entrypoint
- **WHEN** 用户执行 `uv run edera --help`
- **THEN** 系统 SHALL 输出控制 CLI 子命令列表

#### Scenario: Server entrypoint
- **WHEN** 用户执行 `edera-server --config-dir ./config`
- **THEN** 系统 SHALL 启动后端引擎并监听 gRPC 端口

#### Scenario: Web entrypoint
- **WHEN** 用户执行 `edera-web`
- **THEN** 系统 SHALL 启动网页 BFF 进程

#### Scenario: Old project commands removed
- **WHEN** 检查 package console scripts
- **THEN** MUST NOT 存在名为 `stockimformation` 的 console script
- **AND** MUST NOT 存在名为 `rig` 的 console script
- **AND** MUST NOT 存在 `edera`(无参) 启动 web 的隐式语义
