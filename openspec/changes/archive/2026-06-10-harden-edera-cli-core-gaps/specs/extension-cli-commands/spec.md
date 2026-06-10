## ADDED Requirements

### Requirement: workflow extension export 完整性
`edera extension export` SHALL 对 `type: workflow_extension` 导出可重新导入的完整包，providers 和 libraries MUST 按 manifest imports 结构写入 `_providers/` 和 `_lib/`。

#### Scenario: provider manifest 被导出
- **WHEN** 用户执行 `edera extension export default-news-workflow -o pkg.tar.gz`
- **THEN** 导出包 SHALL 为每个 provider 写入 `_providers/<provider>/manifest.yaml`
- **AND** 导出包 SHALL 包含该 provider 的 handler 代码

#### Scenario: library 从 _libs 导出
- **WHEN** workflow extension manifest 包含 `imports.libraries`
- **THEN** CLI SHALL 从已安装 handler 根目录下的 `_libs` 来源复制对应 library 到导出包 `_lib/`
- **AND** CLI SHALL 保留 library 目录结构

#### Scenario: 缺失 provider 或 library 代码
- **WHEN** manifest 声明的 provider 或 library 代码在已安装 handler 根目录中不存在
- **THEN** CLI SHALL 完成可导出的其余内容
- **AND** CLI SHALL 输出 warning 标明未包含的 provider 或 library
