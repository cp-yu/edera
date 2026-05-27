## MODIFIED Requirements

### Requirement: Engine 启动入口
核心 SHALL 提供统一启动入口 `Engine`，接受 `config_dir` 和 `extensions_dirs` 参数，完成 bootstrap 后提供 DAG 执行能力。该入口 SHALL 由 `edera_core` 包导出并由 `edera` console script 调用。

#### Scenario: 最小启动

- **WHEN** 调用 `Engine(config_dir=Path("config"), extensions_dirs=[Path("extensions")])`
- **THEN** 核心 SHALL 完成扫描扩展 → 构建 registry → 加载配置 → 初始化数据库 → 就绪

#### Scenario: edera package entrypoint
- **WHEN** 用户执行 `uv run edera`
- **THEN** console script SHALL 调用 `edera_core.main:main`
- **AND** 核心 bootstrap SHALL 使用 `edera_core` import namespace
