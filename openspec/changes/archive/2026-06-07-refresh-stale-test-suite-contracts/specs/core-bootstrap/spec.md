## MODIFIED Requirements

### Requirement: 扩展目录扫描

核心 SHALL 在启动时扫描配置的 `extensions_dirs` 列表中的所有目录，发现扩展 manifest 并持久化 extension metadata。扫描 MUST 递归一层（扩展目录的直接子目录）。扫描阶段 MUST NOT 构建 `HandlerRegistry` 或 `EntityTypeRegistry`。

#### Scenario: 扫描单个扩展目录

- **WHEN** 核心启动，`extensions_dirs` 配置为 `[Path("extensions")]`
- **THEN** 核心 SHALL 遍历 `extensions/` 下的每个子目录，尝试解析 manifest 或应用 fallback
- **AND** 核心 SHALL 将解析后的 extension metadata 持久化到数据库

#### Scenario: 跳过以下划线开头的目录

- **WHEN** 扫描发现 `extensions/_lib/` 目录
- **THEN** 核心 SHALL 跳过该目录（不视为扩展），但将其加入 Python module path

#### Scenario: 空扩展目录

- **WHEN** `extensions/` 目录为空
- **THEN** 核心 SHALL 正常启动，数据库中无新增 extension metadata
- **AND** DAG 执行时缺失 handler SHALL 由运行期 resolver 按需报错

### Requirement: Handler Registry 构建

核心 SHALL 从 extension manifest 中提取 handler metadata，并将其作为 extension metadata 持久化到数据库。运行时 handler 查询 SHALL 通过 DB-backed resolver 完成。核心 MUST NOT 维护全局 `HandlerRegistry`。

#### Scenario: 注册 handler metadata

- **WHEN** bootstrap 解析到 manifest 声明 handler `name: fetch-rss, entry: handler.py`
- **THEN** 核心 SHALL 将 handler metadata 写入数据库中的 extension metadata
- **AND** 后续 DAG run SHALL 通过 DB-backed resolver 查询该 handler metadata

#### Scenario: Handler 名冲突

- **WHEN** 两个 enabled extension 声明了同名 handler
- **THEN** 核心 SHALL 拒绝使冲突 metadata 同时生效并报告冲突，包含两个扩展的路径或名称

### Requirement: Entity Type Registry 构建

核心 SHALL 从 extension manifest 和配置 schema 中读取 entity type metadata，并将有效 metadata 写入 DB-backed source of truth。核心 MUST NOT 维护全局 `EntityTypeRegistry`。

#### Scenario: 扩展声明新 entity type

- **WHEN** 扩展 manifest 声明 `entity_types: [{name: rss-source, ...}]` 且 DB 中无 `rss-source` 定义
- **THEN** 核心 SHALL 将该 entity type metadata 写入数据库

#### Scenario: 用户配置覆盖扩展声明

- **WHEN** 扩展 manifest 声明 `rss-source` entity type，用户配置也定义了 `rss-source`
- **THEN** 核心 SHALL 使用户配置对应的 metadata 成为 DB-backed source of truth

### Requirement: Engine 启动入口
核心 SHALL 提供统一启动入口 `Engine`，接受 `config_dir` 和 `extensions_dirs` 参数，完成 bootstrap 后提供 DAG 执行能力。运行入口由 `edera`、`edera-server`、`edera-web` 三个 console scripts 分担。

#### Scenario: 最小启动

- **WHEN** 调用 `Engine(config_dir=Path("config"), extensions_dirs=[Path("extensions")])`
- **THEN** 核心 SHALL 完成扫描扩展 → 持久化 extension metadata → 加载配置 → 初始化数据库 → 就绪

#### Scenario: edera CLI entrypoint
- **WHEN** 用户执行 `uv run edera --help`
- **THEN** console script SHALL 调用 `edera_core.cli:main`
- **AND** 核心 bootstrap SHALL 使用 `edera_core` import namespace

### Requirement: Bootstrap 逻辑可重入
核心 bootstrap 逻辑 SHALL 可重入，支持运行时重新扫描 extension metadata 和刷新 DB-backed source of truth。重新执行时 SHALL 不影响正在执行的 DAG。

#### Scenario: 热加载触发重新 bootstrap
- **WHEN** manifest 文件变更触发热加载
- **THEN** 核心 SHALL 重新执行扫描扩展和 metadata 持久化流程

#### Scenario: Metadata 刷新
- **WHEN** 重新 bootstrap 完成
- **THEN** 新 DAG run SHALL 使用更新后的 DB-backed metadata

#### Scenario: 运行中 DAG 不受影响
- **WHEN** 重新 bootstrap 期间有 DAG 正在执行
- **THEN** 该 DAG SHALL 继续使用启动时创建的 `DagExecutionSnapshot`，不受新 metadata 影响
