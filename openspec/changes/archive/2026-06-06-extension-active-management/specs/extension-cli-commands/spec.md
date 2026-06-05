---
capabilities:
  - cap.core.extension-cli-commands
---
# extension-cli-commands Specification

## Purpose
定义 CLI `edera extension` 子命令集，覆盖扩展的 list、show、install、uninstall、reactivate、import、export、export-entities 操作。

## ADDED Requirements

### Requirement: extension list 命令

`edera extension list` SHALL 展示扩展信息。支持 `--available`（扫描 `extensions/` 目录的可用扩展）、`--installed`（查询数据库的已安装扩展）。无 flag 时 SHALL 同时展示两者。

#### Scenario: 列出所有扩展

- **WHEN** 用户执行 `edera extension list`
- **THEN** CLI SHALL 输出已安装扩展（含 name、version、enabled 状态）和可用但未安装的扩展

#### Scenario: 仅列出已安装扩展

- **WHEN** 用户执行 `edera extension list --installed`
- **THEN** CLI SHALL 仅输出 `installed_extensions` 表中的记录

#### Scenario: 仅列出可用扩展

- **WHEN** 用户执行 `edera extension list --available`
- **THEN** CLI SHALL 扫描 `extensions/` 目录，输出所有包含合法 `manifest.yaml` 的子目录

### Requirement: extension show 命令

`edera extension show <name>` SHALL 展示扩展详情，包括 manifest 内容、提供的 handler、entity type、导入的 entity 列表。

#### Scenario: 查看已安装扩展详情

- **WHEN** 用户执行 `edera extension show rss-fetcher` 且该扩展已安装
- **THEN** CLI SHALL 从 `installed_extensions.manifest_snapshot` 读取并展示 manifest 内容
- **AND** CLI SHALL 展示 `import_records` 中的导入记录

#### Scenario: 查看未安装但可用的扩展

- **WHEN** 用户执行 `edera extension show my-ext` 且该扩展存在于 `extensions/` 但未安装
- **THEN** CLI SHALL 从 `extensions/my-ext/manifest.yaml` 读取并展示 manifest 内容

### Requirement: extension install 命令

`edera extension install <name>` SHALL 从 `extensions/` 目录安装扩展。安装 MUST 通过 gRPC 调用 server。

#### Scenario: 安装可用扩展

- **WHEN** 用户执行 `edera extension install rss-fetcher` 且 `extensions/rss-fetcher` 存在
- **THEN** CLI SHALL 调用 `ExtensionService.Install` 完成安装
- **AND** CLI SHALL 输出安装结果（安装的 handler 数量、导入的 entity 数量）

#### Scenario: 扩展不可用

- **WHEN** 用户执行 `edera extension install unknown` 且 `extensions/unknown` 不存在
- **THEN** CLI SHALL 输出错误并以非零状态退出

### Requirement: extension uninstall 命令

`edera extension uninstall <name> --strategy=<strategy>` SHALL 卸载扩展。`--strategy` 参数 MUST 为必填，不提供默认值。

#### Scenario: 使用 purge 策略卸载

- **WHEN** 用户执行 `edera extension uninstall rss-fetcher --strategy=purge`
- **THEN** CLI SHALL 调用 `ExtensionService.Uninstall` 以 purge 策略执行卸载

#### Scenario: 未指定 strategy

- **WHEN** 用户执行 `edera extension uninstall rss-fetcher`（无 `--strategy`）
- **THEN** CLI MUST 输出错误提示用户必须指定 `--strategy=purge|keep-modified|deactivate`

#### Scenario: 卸载存在依赖

- **WHEN** 用户执行卸载且其他已安装扩展依赖此扩展
- **THEN** CLI SHALL 输出依赖关系列表并以非零状态退出

### Requirement: extension reactivate 命令

`edera extension reactivate <name>` SHALL 重新激活已停用的扩展。

#### Scenario: 重新激活已停用扩展

- **WHEN** 用户执行 `edera extension reactivate my-ext` 且该扩展 `enabled=false`
- **THEN** CLI SHALL 调用 `ExtensionService.Reactivate` 并输出成功信息

### Requirement: extension import 命令

`edera extension import <file>` SHALL 从文件导入扩展包到 `extensions/` 目录。支持 `--install` flag 导入后立即安装。

#### Scenario: 导入扩展包

- **WHEN** 用户执行 `edera extension import my-ext.tar.gz`
- **THEN** CLI SHALL 解压到 `extensions/<manifest.name>/`
- **AND** CLI SHALL 输出 "扩展已导入，使用 'edera extension install <name>' 安装"

#### Scenario: 导入并立即安装

- **WHEN** 用户执行 `edera extension import my-ext.tar.gz --install`
- **THEN** CLI SHALL 解压到 `extensions/<manifest.name>/`
- **AND** CLI SHALL 自动执行 install 流程

#### Scenario: 导入文件格式非法

- **WHEN** 用户执行 `edera extension import bad-file.txt` 且文件不包含合法 manifest
- **THEN** CLI MUST 拒绝导入并输出错误

### Requirement: extension export 命令

`edera extension export <name>` SHALL 导出已安装扩展为完整扩展包。

#### Scenario: 导出已安装扩展

- **WHEN** 用户执行 `edera extension export rss-fetcher -o rss-fetcher.tar.gz`
- **THEN** CLI SHALL 打包 manifest（从数据库）、Entity 实例（从数据库生成 YAML）、handler 代码（从 `handlers/` 目录）
- **AND** CLI SHALL 写出 tar.gz 文件

#### Scenario: handler 代码不在 handlers/ 下

- **WHEN** 已安装扩展的 handler 路径指向 `handlers/` 外的位置
- **THEN** 导出包 MUST NOT 包含该 handler 代码
- **AND** CLI SHALL 输出警告提示代码未包含

### Requirement: extension export-entities 命令

`edera extension export-entities` SHALL 从数据库导出指定 entity 子集作为新扩展包。

#### Scenario: 导出 entity 子集

- **WHEN** 用户执行 `edera extension export-entities --entities node:my-node,dag:my-dag --name my-ext --version 1.0.0 -o my-ext.tar.gz`
- **THEN** CLI SHALL 从数据库查询指定 entity
- **AND** CLI SHALL 自动生成 `manifest.yaml`（含 `imports.entities`）
- **AND** CLI SHALL 将 entity 序列化为 YAML 文件
- **AND** CLI SHALL 打包输出，不含 handler 代码

#### Scenario: 指定 entity 不存在

- **WHEN** `--entities` 中包含数据库中不存在的 entity ref
- **THEN** CLI MUST 拒绝导出并报告缺失的 entity
