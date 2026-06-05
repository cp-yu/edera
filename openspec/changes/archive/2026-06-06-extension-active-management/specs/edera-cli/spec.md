---
capabilities:
  - cap.core.edera-cli
---
# edera-cli Delta Specification

## MODIFIED Requirements

### Requirement: CLI binary 入口
系统 SHALL 提供名为 `edera` 的 CLI binary，作为 agent 和人类访问 Edera 控制面能力的统一入口。`edera` 是控制 CLI 的命令名，与 `edera-server`（后端引擎）、`edera-web`（网页 BFF）三个 console scripts 一同构成完整入口集合。

#### Scenario: CLI 可执行

- **WHEN** 用户或 agent 在终端执行 `edera --help`
- **THEN** 系统 SHALL 输出可用子命令列表（entity、node、dag、event、system、client、handler-validate、extension）

#### Scenario: 版本查询

- **WHEN** 用户执行 `edera --version`
- **THEN** 系统 SHALL 输出当前版本号

#### Scenario: Console scripts 集合

- **WHEN** 检查包的 console scripts
- **THEN** 系统 SHALL 注册 `edera = "edera_core.cli:main"`、`edera-server = "edera_core.server:main"`、`edera-web = "edera_core.web.__main__:main"`
- **AND** 系统 SHALL NOT 注册名为 `rig` 的 console script

## ADDED Requirements

### Requirement: Extension 子命令组

`edera extension` SHALL 提供扩展生命周期管理命令集。所有安装/卸载/激活操作 MUST 通过 gRPC 调用 `edera-server`。`import` 和 `export` 命令涉及本地文件操作，MAY 部分离线执行。

#### Scenario: Extension 子命令可用

- **WHEN** 用户执行 `edera extension --help`
- **THEN** 系统 SHALL 输出可用子命令列表（list、show、install、uninstall、reactivate、import、export、export-entities）
