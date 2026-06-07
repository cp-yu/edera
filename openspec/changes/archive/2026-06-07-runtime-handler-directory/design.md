## Context

当前 handler 相关边界有三类状态：`extensions/` 中的可安装来源、`installed_extensions.manifest_snapshot` 中的 metadata、以及运行时实际加载的 handler 文件。实现中启动路径会在数据库为空时自动扫描 `extensions/` 并复制到项目根 `handlers/`，这让启动行为、安装行为和运行权威混在一起。

项目仍处于开发阶段，没有兼容旧安装形态的历史负担。用户确认运行权威应为安装后的 handler 目录，并由首次 agent 或人工一次性复制现有文件，不需要在程序里保留版本迁移脚本。

## Goals / Non-Goals

**Goals:**
- 将 handler 运行权威统一为 `SystemConfig.handlers_dir`，默认 `data/handlers`。
- 移除启动时自动迁移和复制 handler 的路径。
- 保留显式 extension install 作为从 `extensions/` 复制到运行目录的唯一程序入口。
- 让 resolver、controller、export、extension service 使用同一个配置目录。
- 清理规格中的 `HandlerRegistry`、启动扫描安装和 `extensions/` 运行来源漂移。

**Non-Goals:**
- 不实现 handler 版本化目录。
- 不实现旧 `handlers/` 到 `data/handlers/` 的自动迁移。
- 不改变 `installed_extensions` 表结构。
- 不改变 handler manifest schema。
- 不把 `extensions/` 改为运行时加载来源。

## Decisions

### Decision 1: `SystemConfig.handlers_dir` 是运行目录配置

`handlers_dir` 放在现有 `config/system.toml`，默认 `data/handlers`。这是系统运行路径，和 `database_url`、`workspace_root` 同属运行级配置，不需要新增 `config.yaml`。

备选方案：
- 新增 `config.yaml`：被拒绝，会引入第二套全局配置入口。
- 继续用 `config_dir.parent / "handlers"`：被拒绝，默认污染项目根且不体现运行数据边界。

### Decision 2: 显式安装是唯一复制入口

程序只在 `ExtensionManager.install()` 安装扩展时复制 handler 文件。启动、runtime config loading 和 bootstrap 不再调用 `migrate_existing_extensions`。

备选方案：
- 保留开发期自动迁移：被拒绝，行为隐式且和安装模型重复。
- 直接从 `extensions/` 执行：被拒绝，削弱安装/卸载/导出边界。

### Decision 3: 删除迁移脚本

删除 `packages/core/src/edera_core/migration/migrate_extensions.py` 及调用者。现有 handler 文件的首次搬迁由 agent 或人工执行一次，不进入运行时代码。

### Decision 4: 规格术语收敛

`HandlerRegistry` 不再用于描述当前运行模型。新 DAG run 通过 `DagExecutionSnapshot` 冻结 DB-backed resolver metadata，`NodeExecutor` 从 `handlers_dir` 解析并加载 handler。

## Risks / Trade-offs

- [空 DB 启动后扩展不再自动可用] -> 这是预期行为；用户必须显式安装扩展或准备 `installed_extensions` 记录和 `handlers_dir` 文件。
- [已有本地 `handlers/` 不会自动搬迁] -> 由 agent 或人工一次性复制到 `data/handlers/`。
- [运行中 DAG 的代码内容仍依赖已加载 module cache] -> 本变更不引入版本化目录；运行一致性继续由 `DagExecutionSnapshot` metadata 和 `NodeExecutor` module cache 提供。
- [`_lib` 共享覆盖策略仍有限] -> 本变更只把目录权威收敛到 `handlers_dir`，不解决共享库 ownership/version 策略。
