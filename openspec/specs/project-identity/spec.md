---
capabilities:
  - cap.core.project-identity
---
# project-identity Specification

## Purpose
此规约记录变更 rename-project-to-edera 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Canonical project identity
系统 SHALL 使用 `Edera` 作为项目 canonical name，使用 `edera` 作为 canonical slug。OpenSpec project id MUST 为 `proj.edera`，项目描述 MUST 将系统定位为以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核。

#### Scenario: Project metadata uses Edera
- **WHEN** 读取 `openspec/project.opsx.yaml`
- **THEN** `project.name` MUST 为 `Edera`
- **AND** `project.id` MUST 为 `proj.edera`
- **AND** `project.intent` MUST 不再把股票信息管道作为项目身份

### Requirement: Package namespace identity
系统 SHALL 使用 `edera_core` 作为核心 Python import 包，使用 `edera_types` 作为共享 extension protocol import 包。分发包 MUST 分别命名为 `edera-core` 和 `edera-types`。

#### Scenario: Core package import
- **WHEN** 应用代码导入核心运行时
- **THEN** import path MUST 使用 `edera_core`
- **AND** MUST NOT 使用 `stockimformation_core`

#### Scenario: Types package import
- **WHEN** extension handler 导入 `HandlerContext`、`NodeInput` 或 `NodeOutput`
- **THEN** import path MUST 使用 `edera_types`
- **AND** MUST NOT 使用 `stockimformation_types`

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

### Requirement: README name origin
README SHALL 说明 `Edera` 名称来源：`Entity`、`DAG`、`Execution`、`Runtime`、`Architecture`。README 还 SHALL 说明 `edera` 的 ivy（常春藤）隐喻，用于表达连接、攀附、延展，并明确项目定位为通用编排内核。

#### Scenario: README explains Edera
- **WHEN** 用户阅读 `README.md`
- **THEN** 文档 SHALL 包含 `Edera` 名称来源说明
- **AND** 文档 SHALL 包含“以 Entity 为统一原语、以 DAG 为执行模型的通用编排内核”这一定位

### Requirement: Project configuration naming
系统 SHALL 使用 `EDERA_` 作为项目级 runtime settings 环境变量前缀。默认数据库路径、workspace 路径和临时生成目录 MUST 使用 `edera` slug。

#### Scenario: Runtime settings env prefix
- **WHEN** 系统读取 runtime settings
- **THEN** 环境变量前缀 MUST 为 `EDERA_`
- **AND** MUST NOT 读取 `STOCKIMFORMATION_` 作为兼容前缀

#### Scenario: Default runtime paths
- **WHEN** 系统使用默认配置
- **THEN** 默认数据库路径 SHALL 指向 `data/edera.db`
- **AND** 默认 workspace 路径 SHALL 位于 `/tmp/edera/runs`
