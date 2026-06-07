## MODIFIED Requirements

### Requirement: 扩展目录扫描

核心启动 SHALL NOT 自动扫描 `extensions_dirs` 并持久化 extension metadata。可用扩展扫描 SHALL 仅由显式 extension list/show/install 入口触发。扫描阶段 MUST NOT 构建 `HandlerRegistry` 或 `EntityTypeRegistry`。

#### Scenario: 启动不扫描扩展目录

- **WHEN** 核心启动，`extensions_dirs` 配置为 `[Path("extensions")]`
- **THEN** 核心 MUST NOT 遍历 `extensions/` 子目录安装扩展
- **AND** 核心 MUST NOT 将未安装 extension metadata 持久化到数据库

#### Scenario: 跳过以下划线开头的目录

- **WHEN** 显式 extension 扫描发现 `extensions/_lib/` 目录
- **THEN** 核心 SHALL 跳过该目录（不视为扩展）

#### Scenario: 空扩展目录

- **WHEN** `extensions/` 目录为空
- **THEN** 核心 SHALL 正常启动，数据库中无新增 extension metadata
- **AND** DAG 执行时缺失 handler SHALL 由运行期 resolver 按需报错

### Requirement: Module Path 设置

核心 bootstrap SHALL 将配置的 `handlers_dir` 加入 `sys.path`，使已安装 handler 可通过相对 import 引用 `handlers_dir/_lib/` 模块。

#### Scenario: Handler import _lib 模块

- **WHEN** 已安装 handler 代码包含 `from _lib.http_fetch import fetch_with_recovery`
- **THEN** Python 运行时 SHALL 成功解析该 import（因 `handlers_dir` 已在 `sys.path` 中）

### Requirement: Engine 启动入口
核心 SHALL 提供统一启动入口 `Engine`，接受 `config_dir` 和 `extensions_dirs` 参数，完成 bootstrap 后提供 DAG 执行能力。运行入口由 `edera`、`edera-server`、`edera-web` 三个 console scripts 分担。

#### Scenario: 最小启动

- **WHEN** 调用 `Engine(config_dir=Path("config"), extensions_dirs=[Path("extensions")])`
- **THEN** 核心 SHALL 加载配置 → 初始化数据库 → 加载已安装 extension metadata → 就绪
- **AND** 核心 MUST NOT 自动安装 `extensions/` 下的可用扩展

#### Scenario: edera CLI entrypoint
- **WHEN** 用户执行 `uv run edera --help`
- **THEN** console script SHALL 调用 `edera_core.cli:main`
- **AND** 核心 bootstrap SHALL 使用 `edera_core` import namespace

### Requirement: Bootstrap 逻辑可重入
核心 bootstrap 逻辑 SHALL 可重入，支持刷新 DB-backed source of truth 中的已安装 extension metadata。重新执行时 SHALL 不影响正在执行的 DAG。

#### Scenario: 显式 extension lifecycle 触发刷新
- **WHEN** extension install、uninstall 或 reactivate 操作成功
- **THEN** 核心 SHALL 刷新已安装 extension metadata

#### Scenario: Metadata 刷新
- **WHEN** metadata 刷新完成
- **THEN** 新 DAG run SHALL 使用更新后的 DB-backed metadata

#### Scenario: 运行中 DAG 不受影响
- **WHEN** metadata 刷新期间有 DAG 正在执行
- **THEN** 该 DAG SHALL 继续使用启动时创建的 `DagExecutionSnapshot`，不受新 metadata 影响
