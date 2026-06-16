## ADDED Requirements

### Requirement: 运维操作不暴露 Web
Web 控制台（`edera-web`）面向运行态管理（如安装、卸载、查看列表、编辑配置）。凡属于一次性运维操作（非日常运行态管理）、会扩大攻击面（删除源目录、批量写入）或与控制台运行态管理定位不符的操作，SHALL 视为运维操作。运维操作 SHALL 仅经 CLI + gRPC 暴露，MUST NOT 在 `edera-web` 注册 HTTP route。

#### Scenario: 运维操作仅在 CLI+gRPC
- **WHEN** 新增一个删除源目录或批量导入数据的操作
- **THEN** 系统 SHALL 在 gRPC service 实现该操作，并在 `edera` CLI 提供子命令
- **AND** MUST NOT 在 `edera-web` 注册对应 HTTP route

#### Scenario: 运行态管理操作仍暴露 Web
- **WHEN** 操作属于安装、卸载、查看列表、编辑配置等运行态管理
- **THEN** 系统 SHALL 在 `edera-web` 暴露对应 HTTP route（经 `GrpcClient` 透传至 `edera-server`）
