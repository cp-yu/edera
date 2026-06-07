## MODIFIED Requirements

### Requirement: extension export 命令

`edera extension export <name>` SHALL 导出已安装扩展为完整扩展包。

#### Scenario: 导出已安装扩展

- **WHEN** 用户执行 `edera extension export rss-fetcher -o rss-fetcher.tar.gz`
- **THEN** CLI SHALL 打包 manifest（从数据库）、Entity 实例（从数据库生成 YAML）、handler 代码（从配置的 `handlers_dir` 目录）
- **AND** CLI SHALL 写出 tar.gz 文件

#### Scenario: handler 代码不在 handlers_dir 下

- **WHEN** 已安装扩展的 handler 路径指向 `handlers_dir` 外的位置
- **THEN** 导出包 MUST NOT 包含该 handler 代码
- **AND** CLI SHALL 输出警告提示代码未包含
