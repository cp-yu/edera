## Context

当前系统中，skills 配置存储在 `config/skills/*.yaml` 文件中。Skills 是 Agent 执行时可用的能力定义，包含 skill 的名称、描述、prompt 模板等配置。启动时从文件系统加载所有 skills 到 skill registry。

现有机制：
- Skills 通过 `load_skill_configs()` 从 `config/skills/` 目录加载
- 每个 skill 是一个独立的 YAML 文件
- Agent 执行时从 skill registry 获取 skill 配置

系统约束：
- Agent 执行需要 skill 文件存在于文件系统（可能被 Agent 工具读取）
- Skills 总量无上限，但单个运行的 agent node 同时接受的 skills 不超过 50 个
- Skill 配置变更不频繁
- Skill 可以是多文件结构（文件夹），每个 skill 必须包含主文件 `SKILL.md`

## Goals / Non-Goals

**Goals:**
- 移除 `config/skills/*.yaml` 文件，skills 从数据库加载
- 提供 CLI 命令管理 skills
- Agent 执行时从数据库查询 skill 并动态生成临时文件
- 提供 import/export 功能，支持批量迁移和备份
- Skill reload API，刷新运行时 skill 配置

**Non-Goals:**
- 不实现 skill 版本控制
- 不实现 skill 依赖管理
- 不修改 Agent 的 skill 使用方式（仍然读取文件）
- 不实现 skill 的在线编辑器（Web Console 仅支持 CRUD）

## Decisions

### Decision 1: Skills 存储在单表

**决策**：创建 `skills` 表，存储所有 skill 配置。

表结构：
```sql
CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT,
    description TEXT,
    config_body TEXT NOT NULL,  -- JSON: {files: [{path, content}, ...]}
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**config_body 格式**（支持多文件 skill）：
```json
{
  "files": [
    {"path": "SKILL.md", "content": "# Skill content..."},
    {"path": "prompts/main.txt", "content": "..."},
    {"path": "scripts/helper.py", "content": "..."}
  ]
}
```

**选择理由**：
- 单表设计简单，单个 agent node 最多 50 个 skills，JSON 大小可接受
- config_body 存储文件数组，支持多文件 skill（文件夹结构）
- 原子性好：整个 skill 作为整体创建/更新/删除
- 查询效率高：一次查询获取完整 skill，无需 JOIN

### Decision 2: Agent 执行时动态生成 skill 文件

**决策**：Agent 启动时，从数据库查询需要的 skills，生成完整的 skill 文件夹到 session 目录。

流程：
1. Agent 启动前，查询数据库获取所有 skills
2. 为每个 skill 从 config_body.files 数组中遍历，生成所有文件到 `{session_dir}/skills/{skill_name}/` 目录
3. 保持原始文件夹结构（根据 file.path 创建子目录）
4. Agent 执行时读取这些临时文件
5. Session 结束后临时文件保留（用于调试）

**备选方案**：
- A. 动态生成临时文件 → **选择此方案**
- B. Skills 直接注入 Agent prompt → 被拒绝：某些 Agent 工具可能需要读取 skill 文件
- C. 全局临时目录 → 被拒绝：多 Agent 并发执行时可能冲突

**选择理由**：
- 保持 Agent 的文件读取行为不变
- 临时文件与 session 绑定，隔离性好
- 支持多文件 skill，完整还原文件夹结构
- 便于调试和问题排查

### Decision 3: Skill reload API

**决策**：提供 `POST /admin/reload-skills` API，从数据库重新加载 skills。

**选择理由**：
- 与 entity type reload 一致
- 支持运行时更新 skills
- 新启动的 Agent 自动使用最新 skills

### Decision 4: CLI 命令设计

**决策**：新增 `edera skill` 子命令组，支持单文件和多文件（文件夹）skill。

```bash
edera skill list
edera skill show SKILL_NAME

# 创建/更新 skill（从文件夹）
edera skill create --from-dir ./my-skill/
edera skill update SKILL_NAME --from-dir ./my-skill/

# 导入单个 skill 文件夹
edera skill import-dir ./skills/openspec-impact-sweeper/

# 批量导入（扫描目录下所有包含 SKILL.md 的子文件夹）
edera skill import-batch ./skills/

# 导出单个 skill 到文件夹
edera skill export SKILL_NAME -o ./output/

# 删除 skill
edera skill delete SKILL_NAME
```

**选择理由**：
- 支持多文件 skill（文件夹结构）
- `import-dir` 导入单个 skill 文件夹，`import-batch` 批量导入
- `export` 导出为完整文件夹结构
- 与 entity/relation CLI 风格一致

### Decision 5: 用户主动导入策略

**决策**：不自动迁移 skills，用户需要通过 CLI 主动导入。

**选择理由**：
- Skills 数量可能较多，自动迁移可能导致意外行为
- 用户可以选择性导入需要的 skills
- CLI 提供 `import-dir` 和 `import-batch` 支持单个和批量导入
- Web Console 暂不支持多文件 skill 导入，需用户通过 CLI 完成

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| [临时文件生成失败导致 Agent 无法执行] → 生成失败时记录详细错误，Agent 返回明确错误信息 |
| [并发 Agent 生成文件冲突] → 每个 Agent session 使用独立目录，不会冲突 |
| [临时文件占用磁盘空间] → Session 结束后可选清理；提供定期清理策略 |
| [多文件 skill 文件夹结构复杂] → 导入时验证 SKILL.md 存在；存储时保留完整路径信息 |
| [Config JSON 体积过大] → 单个 agent node 最多 50 个 skills，可接受；未来可考虑压缩 |
| [Web Console 不支持多文件 skill] → 明确限制，提示用户使用 CLI；未来可扩展支持 |

## Migration Plan

### 阶段 1：数据库表和 Repository
1. 新增 `Skill` model（支持多文件结构）
2. 新增 skill CRUD 函数
3. 实现文件夹导入/导出逻辑

### 阶段 2：动态文件生成
1. 实现 skill 文件夹生成逻辑（还原完整目录结构）
2. 集成到 Agent 启动流程

### 阶段 3：CLI 和 gRPC
1. 新增 `edera skill` CLI 命令（支持 import-dir, import-batch, export）
2. 新增 gRPC `SkillService`
3. 实现 reload API

### 阶段 4：清理和测试
1. 移除文件系统加载逻辑
2. 更新测试
3. 完整的导入导出测试
4. Web Console 添加多文件 skill 限制提示
