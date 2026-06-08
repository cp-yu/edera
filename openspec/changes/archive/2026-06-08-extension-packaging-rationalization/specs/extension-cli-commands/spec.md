## MODIFIED Requirements

### Requirement: extension export 命令

`edera extension export <name>` SHALL 导出已安装扩展为完整扩展包。对于 `type: workflow_extension`，导出包 MUST 包含 `_providers/` 和 `_lib/` 目录结构。

#### Scenario: 导出已安装扩展

- **WHEN** 用户执行 `edera extension export rss-fetcher -o rss-fetcher.tar.gz`
- **THEN** CLI SHALL 打包 manifest（从数据库）、Entity 实例（从数据库生成 YAML）、handler 代码（从配置的 `handlers_dir` 目录）
- **AND** CLI SHALL 写出 tar.gz 文件

#### Scenario: handler 代码不在 handlers_dir 下

- **WHEN** 已安装扩展的 handler 路径指向 `handlers_dir` 外的位置
- **THEN** 导出包 MUST NOT 包含该 handler 代码
- **AND** CLI SHALL 输出警告提示代码未包含

#### Scenario: 导出 workflow extension 包含 providers

- **WHEN** 用户执行 `edera extension export default-news-workflow -o pkg.tar.gz`
- **THEN** CLI SHALL 从 `manifest_snapshot` 读取 `imports.providers` 列表
- **AND** CLI SHALL 从 `handlers_dir/default-news-workflow.*` 复制所有 provider handler 代码到导出包的 `_providers/` 目录
- **AND** CLI SHALL 为每个 provider 生成独立的 `manifest.yaml`

#### Scenario: 导出 workflow extension 包含 libraries

- **WHEN** 用户执行导出 `type: workflow_extension` 且 manifest 包含 `imports.libraries`
- **THEN** CLI SHALL 从 `handlers_dir/_libs/{package}.*` 复制所有 library 目录到导出包的 `_lib/` 目录
- **AND** 保留 library 的完整目录结构

### Requirement: extension install 命令

`edera extension install <name>` SHALL 从 `extensions/` 目录安装扩展。安装 MUST 通过 gRPC 调用 server。对于 `type: workflow_extension`，系统 MUST 递归安装 `imports.providers` 中的 providers。

#### Scenario: 安装可用扩展

- **WHEN** 用户执行 `edera extension install rss-fetcher` 且 `extensions/rss-fetcher` 存在
- **THEN** CLI SHALL 调用 `ExtensionService.Install` 完成安装
- **AND** CLI SHALL 输出安装结果（安装的 handler 数量、导入的 entity 数量）

#### Scenario: 扩展不可用

- **WHEN** 用户执行 `edera extension install unknown` 且 `extensions/unknown` 不存在
- **THEN** CLI SHALL 输出错误并以非零状态退出

#### Scenario: 安装 workflow extension 递归处理 providers

- **WHEN** 用户执行 `edera extension install default-news-workflow` 且该扩展为 `type: workflow_extension`
- **THEN** CLI SHALL 输出主扩展安装进度
- **AND** CLI SHALL 输出每个 provider 的安装进度（handler 复制、entity 导入）
- **AND** CLI SHALL 输出 library 复制进度
- **AND** 最终输出汇总：主扩展 + N 个 providers，共 M 个 handlers，导入 K 个 entities

#### Scenario: 安装 workflow extension 时 provider 缺失

- **WHEN** manifest 声明的 provider 路径不存在或 manifest 缺失
- **THEN** CLI MUST 拒绝安装并报告缺失的 provider 路径
