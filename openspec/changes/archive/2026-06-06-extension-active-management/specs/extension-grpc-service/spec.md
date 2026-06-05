---
capabilities:
  - cap.core.extension-grpc-service
---
# extension-grpc-service Specification

## Purpose
定义 gRPC ExtensionService，提供扩展管理 RPC 接口，支撑 CLI 和 WebConsole 的扩展管理操作。

## ADDED Requirements

### Requirement: ExtensionService proto 定义

`edera.proto` SHALL 新增 `ExtensionService`，包含 `ListAvailable`、`ListInstalled`、`Show`、`Install`、`Uninstall`、`Reactivate` RPC。

#### Scenario: proto 定义包含所有 RPC

- **WHEN** 检查 `proto/edera.proto` 中 `ExtensionService` 定义
- **THEN** 该 service MUST 包含 `ListAvailable`、`ListInstalled`、`Show`、`Install`、`Uninstall`、`Reactivate` RPC 方法

### Requirement: ListAvailable RPC

`ExtensionService.ListAvailable` SHALL 扫描 `extensions/` 目录返回所有可用扩展的 manifest 摘要。

#### Scenario: 返回可用扩展列表

- **WHEN** 客户端调用 `ListAvailable`
- **THEN** server SHALL 扫描 `extensions/` 目录
- **AND** 对每个含合法 `manifest.yaml` 的子目录返回 `name`、`version`、`description`、`depends`

### Requirement: ListInstalled RPC

`ExtensionService.ListInstalled` SHALL 查询 `installed_extensions` 表返回所有已安装扩展。

#### Scenario: 返回已安装扩展列表

- **WHEN** 客户端调用 `ListInstalled`
- **THEN** server SHALL 查询 `installed_extensions` 表
- **AND** 返回每条记录的 `name`、`version`、`enabled`、`installed_by`、`created_at`

### Requirement: Install RPC

`ExtensionService.Install` SHALL 执行扩展安装流程，包括 manifest 校验、依赖检查、代码复制、数据库写入和 Entity 导入。

#### Scenario: 安装成功

- **WHEN** 客户端调用 `Install(name="rss-fetcher")` 且 `extensions/rss-fetcher` 存在
- **THEN** server SHALL 执行完整安装流程
- **AND** 返回安装结果（handler 数量、导入的 entity 数量）

#### Scenario: 安装失败回滚

- **WHEN** 安装过程中 Entity 导入失败
- **THEN** server SHALL 回滚已写入的 `installed_extensions` 记录和已创建的扩展表
- **AND** server SHALL 删除已复制到 `handlers/` 的代码

### Requirement: Uninstall RPC

`ExtensionService.Uninstall` SHALL 接收扩展名和卸载策略，执行对应的卸载流程。

#### Scenario: Uninstall 依赖检查

- **WHEN** 客户端调用 `Uninstall(name="rss-fetcher")` 且其他扩展依赖它
- **THEN** server SHALL 返回错误，包含依赖该扩展的扩展名列表

#### Scenario: Uninstall 策略执行

- **WHEN** 客户端调用 `Uninstall(name="rss-fetcher", strategy="purge")`
- **THEN** server SHALL 按 purge 策略执行卸载
- **AND** 返回卸载结果（删除的 entity 数量、删除的表数量）

### Requirement: Reactivate RPC

`ExtensionService.Reactivate` SHALL 将已停用的扩展重新激活。

#### Scenario: 重新激活成功

- **WHEN** 客户端调用 `Reactivate(name="my-ext")` 且该扩展 `enabled=false`
- **THEN** server SHALL 设置 `enabled=true` 并重新注册 handler 和 entity type
- **AND** 返回成功
