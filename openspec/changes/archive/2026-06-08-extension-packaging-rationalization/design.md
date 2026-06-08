## Context

当前扩展系统采用扁平化目录结构，所有扩展直接放置在 `extensions/` 下。存在以下问题：

1. **包归属不明确**：`default-news-workflow` 依赖 6 个 handler provider 扩展和 1 个共享库，但从目录结构看不出归属关系
2. **Manifest 维护成本高**：uzi-skill 需手动列举 59 个 entity imports，任何新增文件都需修改 manifest
3. **Handler 命名冲突风险**：所有 handler 安装到同一个 `data/handlers/` 扁平目录，不同包的同名 handler 会冲突
4. **依赖解析复杂**：provider 扩展的 `depends: [_lib/http_fetch]` 依赖关系需跨目录解析

当前扩展分类：
- **Handler Provider Extensions**（7 个）：rss-fetcher, api-fetcher, reader, advisor, briefing-generator, notifier, web-scraper
- **Shared Library**（1 个）：_lib/http_fetch
- **Workflow Extensions**（2 个）：default-news-workflow（依赖上述 7+1），uzi-skill（自包含）

## Goals / Non-Goals

**Goals:**
- 将扩展系统重组为**分包结构**，两个顶层 Workflow Extension 包各自管理内部 providers 和 libraries
- Manifest schema 支持 `type: workflow_extension`、`imports.providers`、`imports.libraries`
- Manifest `imports.entities` 支持 glob patterns，消除手动列举维护负担
- Handler 使用命名空间路径 `{package}.{handler}` 避免冲突
- 保持运行时行为不变（DAG 执行、entity 查询、handler 调用逻辑不变）

**Non-Goals:**
- 不改变 entity 数据库存储结构（仍为 per-type tables）
- 不改变 extension 的安装/卸载契约（仍基于 `installed_extensions` 表）
- 不添加 extension 依赖版本管理或冲突检测
- 不支持跨包 provider 共享（每个包的 providers 仅供包内使用）

## Decisions

### 决策 1：采用 Package 命名空间而非嵌套目录

**选择：** Handler 安装到 `data/handlers/{package}.{provider}/`

**替代方案：**
- 方案 A：扁平化 `data/handlers/{provider}/`（现状）
- 方案 B：嵌套目录 `data/handlers/{package}/{provider}/`

**理由：**
- 方案 A 存在同名冲突风险（不同包的 `reader` handler）
- 方案 B 需修改 handler resolver 的多级路径查找逻辑，复杂度高
- 方案 Package 命名空间平衡了命名冲突解决和路径查找简单性

### 决策 2：Glob Patterns 使用 Python `glob` 模块

**选择：** 使用标准库 `glob.glob(pattern, recursive=True)` 展开 manifest imports

**替代方案：**
- 手动实现 glob 语义（支持 `**`, `*`, `?`）
- 使用 `pathspec` 或 `wcmatch` 第三方库

**理由：**
- 标准库 `glob` 已支持 `**` 递归匹配（Python 3.5+）
- 无需引入外部依赖，降低维护成本
- 功能足够覆盖当前需求（`entities/**/*.yaml`, `_providers/*/manifest.yaml`）

### 决策 3：Workflow Extension 内部 Provider 相对路径依赖

**选择：** Provider 的 `depends: [_lib/http_fetch]` 相对于包根路径解析

**实现：**
- 读取 provider manifest 时，检测 `depends` 中以 `_lib/` 开头的依赖
- 解析为 `{package}.{lib_name}`（如 `default-news-workflow.http_fetch`）
- 安装时将 `_lib/http_fetch/` 复制到 `data/libs/default-news-workflow.http_fetch/`

**理由：**
- 避免跨包依赖复杂性（每个包自包含其 _lib）
- 保持 provider manifest 语义不变（现有 `depends: [_lib/http_fetch]` 仍有效）

### 决策 4：Big Bang 迁移而非渐进式

**选择：** 一次性重组目录结构、更新所有 manifest、重装所有扩展

**替代方案：**
- 渐进式迁移：保留旧结构，逐步迁移扩展
- 双轨并行：两种结构同时支持

**理由：**
- 项目处于开发阶段，无历史负担
- 一次性迁移架构清晰，无兼容性代码维护成本
- 使用 subagent 自动化迁移，人工成本可控

### 决策 5：Glob 展开时机为安装时

**选择：** Manifest `imports.entities` 的 glob patterns 在 `edera extension install` 时展开并记录到 `installed_extensions.import_records`

**替代方案：**
- 运行时每次读取时展开

**理由：**
- 安装时展开可验证所有 entity 文件存在，提前发现缺失文件
- `import_records` 记录实际导入的文件列表，支持 uninstall 时精确清理
- 运行时不需要重复 glob 匹配，性能更优

## Risks / Trade-offs

### 风险 1：Glob 实现 bug 导致 entity 漏导入

**影响：** HIGH - 部分 entity 未导入会导致 DAG 无法运行

**缓解措施：**
- 迁移后对比 entity 数量（预期 default: 14, uzi-skill: 59）
- 逐一验证关键 entity（default DAG, uzi-skill-analysis DAG）
- 单元测试覆盖 glob 展开逻辑（`**/*.yaml`, `*/manifest.yaml`）

### 风险 2：已安装扩展数据丢失

**影响：** HIGH - 用户已配置的 entity instances 和 DAG 运行历史

**缓解措施：**
- 迁移前导出所有扩展状态 `edera extension list --json`
- 备份 `extensions/` 目录和 `data/` 目录
- Entity 数据在数据库中，重装扩展不影响已有 entity instances（仅重新导入 seed entities）

### 风险 3：Handler 路径变更导致运行时查找失败

**影响：** MEDIUM - 已提交的 DAG run 可能引用旧 handler 路径

**缓解措施：**
- `DatabaseHandlerResolver` 同时支持新旧路径查找（兼容期）
- 迁移后运行完整回归测试（default DAG, uzi-skill DAG）
- 清理旧 `data/handlers/` 目录，确保仅使用新路径

### 权衡 1：Manifest 简化 vs 显式控制

**权衡：** Glob patterns 简化 manifest（70 行 → 15 行），但丧失显式列举带来的可见性

**决策：** 简化优先
- 59 个手动列举的维护成本远高于可见性收益
- 开发者可通过 `find entities/ -name "*.yaml"` 查看实际文件列表
- `edera extension show` 命令可展示已导入的 entity 列表

### 权衡 2：命名空间路径 vs 嵌套目录

**权衡：** `{package}.{handler}` 扁平路径 vs `{package}/{handler}/` 嵌套目录

**决策：** 命名空间路径优先
- Handler resolver 只需单级路径查找，实现简单
- 路径长度略增（`default-news-workflow.rss-fetcher`），但可读性仍可接受
- 避免多级目录遍历的性能开销

### 权衡 3：一次性迁移 vs 渐进式迁移

**权衡：** Big Bang 停机风险 vs 渐进式的兼容性代码负担

**决策：** Big Bang 迁移
- 开发阶段可承受短暂停机
- 无历史兼容性负担，架构更清晰
- Subagent 自动化迁移降低人工风险
