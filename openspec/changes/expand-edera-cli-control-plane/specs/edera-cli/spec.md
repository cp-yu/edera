---
capabilities:
  - cap.core.edera-cli
---
## MODIFIED Requirements

### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。

#### Scenario: CLI 可执行

- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、relation、entity-type、node、node-type、skill、dag、event、system、client、config、query、source、handler、handler-validate、extension）

#### Scenario: 版本查询

- **WHEN** 用户执行 `edera --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Console scripts 集合

- **WHEN** 检查包的 console scripts
- **THEN** 系统 SHALL 注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`
- **AND** 系统 SHALL NOT 注册名为 `rig` 的 console script
