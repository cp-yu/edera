# extension-grpc-service Specification

## Purpose
此规约记录变更 extension-active-management 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: ExtensionService proto 定义

`edera.proto` SHALL 定义 `ExtensionService`，包含 `ListAvailable`、`ListInstalled`、`Show`、`Install`、`Uninstall`、`Reactivate`、`Delete`、`ImportEntities` RPC。`Install` SHALL 通过专用请求消息接收 overwrite 语义，覆盖安装由请求字段显式触发，默认值为不覆盖。

#### Scenario: proto 定义包含所有 RPC

- **WHEN** 检查 `proto/edera.proto` 中 `ExtensionService` 定义
- **THEN** 该 service MUST 包含 `ListAvailable`、`ListInstalled`、`Show`、`Install`、`Uninstall`、`Reactivate`、`Delete`、`ImportEntities` RPC 方法

#### Scenario: Install 请求携带 overwrite 字段

- **WHEN** 检查 `Install` RPC 的请求消息定义
- **THEN** 该消息 MUST 包含 `name` 与 `overwrite`（布尔，默认 false）字段

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

`ExtensionService.Install` SHALL 执行扩展安装流程，包括 manifest 校验、依赖检查、代码复制、数据库写入和 Entity 导入。当请求携带 `overwrite=true` 时，SHALL 对已安装 extension 执行覆盖安装路径（drop 扩展表、清空并重导 import_records、重建 handler/libs、upsert 记录）；`overwrite=false` 时对已安装 extension MUST 拒绝。覆盖安装结果 SHALL 包含数据保留提醒。

#### Scenario: 安装成功

- **WHEN** 客户端调用 `Install(name="rss-fetcher", overwrite=false)` 且 `extensions/rss-fetcher` 存在且未安装
- **THEN** server SHALL 执行完整安装流程
- **AND** 返回安装结果（handler 数量、导入的 entity 数量）

#### Scenario: 默认安装已存在扩展被拒绝

- **WHEN** 客户端调用 `Install(name="rss-fetcher", overwrite=false)` 且该扩展已安装
- **THEN** server SHALL 返回 `FAILED_PRECONDITION` 错误，提示扩展已安装

#### Scenario: 覆盖安装刷新运行态

- **WHEN** 客户端调用 `Install(name="rss-fetcher", overwrite=true)` 且该扩展已安装
- **THEN** server SHALL 执行覆盖安装路径
- **AND** 返回结果 SHALL 包含 `overwrite=true` 与数据保留提醒

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

### Requirement: InstallExtension RPC 支持 workflow extension

`ExtensionService.Install` RPC MUST 识别 manifest `type: workflow_extension` 并递归处理 `imports.providers` 和 `imports.libraries`。所有 glob patterns MUST 在安装时展开。

#### Scenario: 安装 handler provider extension

- **WHEN** gRPC client 调用 `InstallExtension(name="rss-fetcher")`
- **THEN** server SHALL 读取 `extensions/rss-fetcher/manifest.yaml`
- **AND** server SHALL 写入 `installed_extensions` 表
- **AND** server SHALL 复制 handler 代码到 `handlers_dir/rss-fetcher/`
- **AND** server SHALL 导入 manifest 声明的 entities

#### Scenario: 安装 workflow extension 递归处理 providers

- **WHEN** gRPC client 调用 `InstallExtension(name="default-news-workflow")` 且 manifest 包含 `type: workflow_extension`
- **THEN** server SHALL 展开 `imports.providers` 的 glob patterns
- **AND** server SHALL 递归读取每个 provider 的 manifest
- **AND** server SHALL 将每个 provider 的 handler 代码复制到 `handlers_dir/{package}.{provider}/`
- **AND** server SHALL 记录所有 provider handlers 到主扩展的 `manifest_snapshot`

#### Scenario: 安装 workflow extension 复制 libraries

- **WHEN** manifest 包含 `imports.libraries: ["_lib/*"]`
- **THEN** server SHALL 展开 glob pattern
- **AND** server SHALL 将每个 library 目录复制到 `handlers_dir/_libs/{package}.{library}/`
- **AND** server SHALL 记录 library 路径到 `manifest_snapshot`

#### Scenario: 安装时 glob pattern 无匹配

- **WHEN** manifest 包含 glob pattern 但无任何匹配路径
- **THEN** server MUST 拒绝安装
- **AND** 返回 gRPC error 包含未匹配的 pattern

#### Scenario: Provider 依赖解析失败

- **WHEN** provider manifest 声明 `depends: ["_lib/http_fetch"]` 但主扩展未在 `imports.libraries` 中包含该 library
- **THEN** server MUST 拒绝安装
- **AND** 返回 gRPC error 包含缺失的依赖路径

### Requirement: Delete RPC

`ExtensionService.Delete` SHALL 删除 extensions 写入目录下的 `extensions/<name>` 源目录。该 RPC MUST 仅针对未安装的 extension：若 `installed_extensions` 存在该 name 的记录，SHALL 返回 `FAILED_PRECONDITION` 拒绝删除。该 RPC MUST NOT 提供绕过未安装检查的参数。

#### Scenario: 删除未安装扩展源目录

- **WHEN** 客户端调用 `Delete(name="foo")` 且 `foo` 未安装且源目录存在
- **THEN** server SHALL 删除 `extensions/foo/` 目录
- **AND** 返回删除确认

#### Scenario: 删除已安装扩展被拒绝

- **WHEN** 客户端调用 `Delete(name="foo")` 且 `foo` 已安装
- **THEN** server SHALL 返回 `FAILED_PRECONDITION` 错误，提示先卸载

#### Scenario: 删除不存在的源目录

- **WHEN** 客户端调用 `Delete(name="foo")` 且源目录不存在
- **THEN** server SHALL 返回 `NOT_FOUND` 错误

### Requirement: ImportEntities RPC

`ExtensionService.ImportEntities` SHALL 接收扩展导出压缩包（`export-entities` 产物：含 `manifest.yaml` 与 `entities/*.yaml` 的 tar 包），解包后按 entity id 执行 upsert 导入，返回 imported 与 updated 计数。该 RPC 用于覆盖安装后由用户自行恢复运行时 Entity 数据。

#### Scenario: 导入实体数据按 id upsert

- **WHEN** 客户端调用 `ImportEntities` 提供合法的导出压缩包
- **THEN** server SHALL 解包并读取压缩包内的 Entity 文档
- **AND** 对每个 Entity 按 id 执行 upsert（已存在则更新，不存在则新建）
- **AND** 返回 imported 与 updated 计数

#### Scenario: 导入包格式不合法被拒绝

- **WHEN** 客户端调用 `ImportEntities` 提供的压缩包不含 `manifest.yaml` 或含多个 manifest
- **THEN** server SHALL 返回 `INVALID_ARGUMENT` 错误

