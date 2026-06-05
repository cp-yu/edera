## Context

当前系统通过 `scan_extensions()` 在启动时自动扫描 `extensions/` 目录，将所有扩展的 handler、entity type 和 entity 实例一次性加载。用户无法选择性激活扩展，也无法通过 CLI 或 WebConsole 管理扩展的安装状态。`extensions/` 文件夹同时承担"扩展包仓库"和"运行时代码源"双重角色，导致架构职责不清。

系统中存在两类内容：声明式内容（Entity Type schema、Entity 实例、DAG 定义等）天然适合数据库存储；命令式内容（handler Python 代码）天然属于文件系统。本设计接受这一双源现实，通过明确目录职责来消除歧义。

## Goals / Non-Goals

**Goals:**
- 扩展加载改为主动安装模式，数据库记录安装状态
- `extensions/` 退化为只读扩展包仓库，`handlers/` 作为运行时代码目录
- 提供完整的 CLI 扩展管理命令和 WebConsole 管理界面
- 支持扩展导入（从文件）、导出（含指定 entity 子集导出为新扩展）
- 卸载提供三种策略，用户必须显式选择
- `installed_extensions` 表合并原 `extension_imports` 的功能

**Non-Goals:**
- 扩展版本冲突管理和自动升级
- 扩展市场或远程仓库
- Handler 代码存储在数据库中
- 运行时动态安装（需要热加载但不需要零停机）

## Decisions

### Decision 1: 目录职责分离

`extensions/` 只作为扩展包仓库（可删除不影响运行），`handlers/` 作为运行时代码目录。安装时将 handler 代码从 `extensions/<name>/` 复制到 `handlers/<name>/`。

**备选方案：**
- A. 直接引用 `extensions/` 中的代码 → 被拒绝：`extensions/` 不能被删除，角色歧义
- B. 代码存数据库，运行时 exec() → 被拒绝：安全风险，难以调试，无法处理相对导入

**选择理由：** 接受文件系统是代码的 Source of Truth，数据库是配置/数据的 Source of Truth。handler 路径允许指向 `handlers/` 外的任意位置，但导出时仅打包 `handlers/` 下的代码。

### Decision 2: `installed_extensions` 合并 `extension_imports`

用单表 `installed_extensions` 管理扩展安装状态，导入记录以 `import_records` JSON 字段内嵌。

```sql
CREATE TABLE installed_extensions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT UNIQUE NOT NULL,
    version           TEXT NOT NULL,
    manifest_snapshot TEXT NOT NULL,       -- JSON: 完整 manifest 内容
    import_records    TEXT NOT NULL DEFAULT '[]',  -- JSON array: 导入记录
    enabled           BOOLEAN DEFAULT TRUE,
    installed_by      TEXT,               -- 'cli' | 'webconsole'
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
```

`import_records` JSON 结构：
```json
[
  {
    "import_path": "entities/dags/default.yaml",
    "entity_type": "dag",
    "entity_id": "default",
    "entity_ref": "dag:default",
    "content_digest": "sha256...",
    "imported_entity_digest": "sha256...",
    "status": "imported"
  }
]
```

**备选方案：** 保留两个独立表（`installed_extensions` + `extension_imports`）→ 被拒绝：一个扩展的完整信息应在一行中表达，简化查询和导出。

### Decision 3: Bootstrap 流程重构

启动流程分为两步：
1. `discover_available_extensions()` — 扫描 `extensions/` 构建可用扩展列表（仅用于 CLI/WebConsole 展示）
2. `load_installed_extensions()` — 查询 `installed_extensions` 表，对每个 `enabled=true` 的扩展从 `manifest_snapshot` 恢复 handler 注册和 entity type 注册

Entity 实例和扩展表已在数据库中，由 Repository 层正常加载，无需额外步骤。`load_installed_extensions()` 只负责构建 `HandlerRegistry`（handler name → code path）和 `EntityTypeRegistry`（type name → schema）这两个内存注册表。

### Decision 4: 卸载策略无默认值

卸载时 `--strategy` 参数为必填，不提供默认行为：
- `purge`: 清空所有导入的 Entity（无论是否修改）+ 删除扩展表 + 删除 handler 代码
- `keep-modified`: 保留用户修改过的 Entity，删除未修改的 + 保留扩展表 + 删除 handler 代码
- `deactivate`: 仅设置 `enabled=false`，不删除任何数据和代码

**选择理由：** 数据删除是不可逆操作，强制用户明确意图。

### Decision 5: 依赖检查阻止卸载

卸载前查询所有已安装扩展的 `manifest_snapshot.depends`，如果存在依赖此扩展的其他已安装扩展，阻止卸载并列出依赖者。

### Decision 6: 导出覆盖两种场景

- `edera extension export <name>` — 打包完整扩展（manifest 从数据库 + handler 代码从 `handlers/` + entity 实例从数据库生成 YAML）
- `edera extension export-entities` — 从数据库导出指定 entity 子集，自动生成 manifest，不含 handler 代码

## Risks / Trade-offs

- [Handler 代码与数据库不同步] → 代码只能通过"重新安装"更新，安装流程覆盖 `handlers/` 中的旧文件。用户直接修改 `handlers/` 下的代码会导致与 `extensions/` 不一致，但系统不阻止这一行为。
- [迁移兼容性] → 现有部署的扩展已通过自动扫描加载，迁移时需要自动将当前 `extensions/` 下所有扩展注册到 `installed_extensions` 表。
- [`_lib/` 共享库处理] → 多个扩展可能依赖 `_lib/` 下的共享代码，安装时需要将 `_lib/` 一并复制到 `handlers/_lib/`，卸载时不能随意删除共享库。
- [热加载复杂度] → 安装/卸载后需要热更新内存中的 HandlerRegistry 和 EntityTypeRegistry，需与现有 hot_reload 机制协调。
