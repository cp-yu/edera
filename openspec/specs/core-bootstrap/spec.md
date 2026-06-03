---
capabilities:
  - cap.core.extension-manifest-system
---
# core-bootstrap Specification

## Purpose
此规约记录变更 core-extension-separation 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: 扩展目录扫描

核心 SHALL 在启动时扫描配置的 `extensions_dirs` 列表中的所有目录，发现扩展并构建全局 registry。扫描 MUST 递归一层（扩展目录的直接子目录）。

#### Scenario: 扫描单个扩展目录

- **WHEN** 核心启动，`extensions_dirs` 配置为 `[Path("extensions")]`
- **THEN** 核心 SHALL 遍历 `extensions/` 下的每个子目录，尝试解析 manifest 或应用 fallback

#### Scenario: 跳过以下划线开头的目录

- **WHEN** 扫描发现 `extensions/_lib/` 目录
- **THEN** 核心 SHALL 跳过该目录（不视为扩展），但将其加入 Python module path

#### Scenario: 空扩展目录

- **WHEN** `extensions/` 目录为空
- **THEN** 核心 SHALL 正常启动，handler registry 为空，DAG 执行时按需报错

### Requirement: Handler Registry 构建

核心 SHALL 维护全局 handler registry，映射 handler 名到加载信息（模块路径 + 函数名）。Registry MUST 在 bootstrap 完成后不可变。

#### Scenario: 注册 handler

- **WHEN** bootstrap 解析到 manifest 声明 handler `name: fetch-rss, entry: handler.py`
- **THEN** 核心 SHALL 在 registry 中注册 `"fetch-rss" → (extensions/rss-fetcher/handler.py, "run")`

#### Scenario: Handler 名冲突

- **WHEN** 两个扩展声明了同名 handler
- **THEN** 核心 SHALL 拒绝启动并记录冲突错误，包含两个扩展的路径

### Requirement: Entity Type Registry 构建

核心 SHALL 合并所有扩展声明的 entity types 和用户 `config/` 中的 entity type 定义，用户配置优先级高于扩展声明。

#### Scenario: 扩展声明新 entity type

- **WHEN** 扩展 manifest 声明 `entity_types: [{name: rss-source, ...}]` 且用户 config 中无 `rss-source` 定义
- **THEN** 核心 SHALL 使用扩展声明的定义注册该 entity type

#### Scenario: 用户配置覆盖扩展声明

- **WHEN** 扩展 manifest 声明 `rss-source` entity type，用户 `config/schemas/` 中也定义了 `rss-source`
- **THEN** 核心 SHALL 使用用户配置的定义，忽略扩展声明

### Requirement: Module Path 设置

核心 bootstrap SHALL 将 `extensions/` 目录加入 `sys.path`，使扩展 handler 可通过相对 import 引用 `_lib/` 模块。

#### Scenario: Handler import _lib 模块

- **WHEN** handler 代码包含 `from _lib.http_fetch import fetch_with_recovery`
- **THEN** Python 运行时 SHALL 成功解析该 import（因 `extensions/` 已在 `sys.path` 中）

### Requirement: Engine 启动入口
核心 SHALL 提供统一启动入口 `Engine`，接受 `config_dir` 和 `extensions_dirs` 参数，完成 bootstrap 后提供 DAG 执行能力。运行入口由 `edera`、`edera-server`、`edera-web` 三个 console scripts 分担。

#### Scenario: 最小启动

- **WHEN** 调用 `Engine(config_dir=Path("config"), extensions_dirs=[Path("extensions")])`
- **THEN** 核心 SHALL 完成扫描扩展 → 构建 registry → 加载配置 → 初始化数据库 → 就绪

#### Scenario: edera CLI entrypoint
- **WHEN** 用户执行 `uv run edera --help`
- **THEN** console script SHALL 调用 `edera_core.cli:main`
- **AND** 核心 bootstrap SHALL 使用 `edera_core` import namespace

### Requirement: Bootstrap 逻辑可重入
核心 bootstrap 逻辑 SHALL 可重入，支持运行时重新执行扫描和 registry 构建。重新执行时 SHALL 原子替换 handler registry 和 entity type registry，不影响正在执行的 DAG。

#### Scenario: 热加载触发重新 bootstrap
- **WHEN** manifest 文件变更触发热加载
- **THEN** 核心 SHALL 重新执行扫描扩展、构建 registry 流程

#### Scenario: Registry 原子替换
- **WHEN** 重新 bootstrap 完成
- **THEN** 核心 SHALL 原子替换全局 handler registry 和 entity type registry，新 DAG run 使用新 registry

#### Scenario: 运行中 DAG 不受影响
- **WHEN** 重新 bootstrap 期间有 DAG 正在执行
- **THEN** 该 DAG SHALL 继续使用启动时的 registry 快照，不受新 registry 影响
