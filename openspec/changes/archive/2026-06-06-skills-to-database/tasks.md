# Implementation Tasks

### Task 1: 创建 Skills 数据库表

**Goal**: 创建 `skills` 表存储 skill 配置，支持多文件结构。

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Create: `packages/core/src/edera_core/storage/migrations/0012_skills.py`
- Test: `packages/core/tests/test_skills_storage.py`

**Requirements**:
- 定义 `Skill` SQLModel 类
- 包含字段：id, name, display_name, description, config_body, created_at, updated_at
- config_body 存储 JSON 格式：`{files: [{path, content}, ...]}`
- name 字段添加唯一约束

#### Checks

- [x] C1 验证表创建
  - Verifies: `specs/skill-database-storage/spec.md` / Requirement "Skills 存储到数据库" / Scenario "创建 skill"
  - Command: `pytest packages/core/tests/test_skills_storage.py::test_create_table -v`
  - Expect: 表创建成功

### Task 2: 实现 skill CRUD

**Goal**: 实现 skill 的数据库 CRUD 操作，支持多文件结构。

**Files**:
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `packages/core/tests/test_skill_repository.py`

**Requirements**:
- 实现 `create_skill()`, `update_skill()`, `delete_skill()`, `list_skills()`
- Files 数组序列化为 JSON 存储到 config_body
- 创建时验证 SKILL.md 存在于 files 数组中

#### Checks

- [x] C2 验证创建 skill
  - Verifies: `specs/skill-database-storage/spec.md` / Requirement "Skills 存储到数据库" / Scenario "创建 skill"
  - Command: `pytest packages/core/tests/test_skill_repository.py::test_create_skill -v`
  - Expect: Skill 创建成功，验证 SKILL.md 存在

- [x] C3 验证查询所有 skills
  - Verifies: `specs/skill-database-storage/spec.md` / Requirement "Skills 存储到数据库" / Scenario "查询所有 skills"
  - Command: `pytest packages/core/tests/test_skill_repository.py::test_list_skills -v`
  - Expect: 返回所有 skills，反序列化 files 数组

### Task 3: 实现 skill 动态文件生成

**Goal**: Agent 启动时从数据库生成完整的 skill 文件夹到临时目录。

**Files**:
- Create: `packages/core/src/edera_core/skills/generator.py`
- Modify: `packages/core/src/edera_core/node/executor.py`
- Test: `packages/core/tests/test_skill_generator.py`

**Requirements**:
- 实现 `generate_skill_files(session_dir, skills)` 函数
- 遍历每个 skill 的 config_body.files 数组
- 为每个 skill 创建 `{session_dir}/skills/{skill_name}/` 目录
- 根据 file.path 创建子目录结构，生成文件
- 在 Agent 启动前调用生成函数

#### Checks

- [x] C4 验证生成 skill 文件夹
  - Verifies: `specs/skill-dynamic-generation/spec.md` / Requirement "Agent 执行时生成 skill 文件" / Scenario "生成 skill 文件夹到 session 目录"
  - Command: `pytest packages/core/tests/test_skill_generator.py::test_generate_files -v`
  - Expect: 文件夹和所有文件生成成功

- [x] C5 验证文件内容一致
  - Verifies: `specs/skill-dynamic-generation/spec.md` / Requirement "Agent 执行时生成 skill 文件" / Scenario "Skill 文件内容与数据库一致"
  - Command: `pytest packages/core/tests/test_skill_generator.py::test_content_consistency -v`
  - Expect: 文件内容与数据库一致，路径结构正确

### Task 4: 实现 skill import/export

**Goal**: 实现 skills 的文件夹导入导出。

**Files**:
- Create: `packages/core/src/edera_core/skills/import_export.py`
- Test: `packages/core/tests/test_skill_import_export.py`

**Requirements**:
- 实现 `import_skill_dir(dir_path)` 从单个文件夹导入
- 实现 `import_skills_batch(base_dir)` 批量导入（扫描子文件夹，识别包含 SKILL.md 的文件夹）
- 实现 `export_skill(name, output_dir)` 导出单个 skill 为文件夹
- 导入时验证 SKILL.md 存在
- 导出时保持原始目录结构

#### Checks

- [x] C6 验证导入单个 skill 文件夹
  - Verifies: `specs/skill-database-storage/spec.md` / Requirement "从文件夹导入 skills" / Scenario "导入单个 skill 文件夹"
  - Command: `pytest packages/core/tests/test_skill_import_export.py::test_import_skill_dir -v`
  - Expect: 文件夹内容导入成功，SKILL.md 验证通过

- [x] C7 验证批量导入 skills
  - Verifies: `specs/skill-database-storage/spec.md` / Requirement "从文件夹导入 skills" / Scenario "批量导入多个 skill 文件夹"
  - Command: `pytest packages/core/tests/test_skill_import_export.py::test_import_skills_batch -v`
  - Expect: 识别并导入所有包含 SKILL.md 的子文件夹

- [x] C8 验证导出 skill
  - Verifies: `specs/skill-database-storage/spec.md` / Requirement "导出 skills 到文件夹" / Scenario "导出单个 skill"
  - Command: `pytest packages/core/tests/test_skill_import_export.py::test_export_skill -v`
  - Expect: 生成完整文件夹结构，所有文件正确

### Task 5: 实现 edera skill CLI

**Goal**: 实现 `edera skill` 子命令组，支持多文件 skill 操作。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Create: `packages/core/src/edera_core/cli/skill_commands.py`
- Test: `packages/core/tests/test_cli_skill.py`

**Requirements**:
- 实现 `list`, `show` 命令
- 实现 `create --from-dir`, `update --from-dir` 命令
- 实现 `import-dir`, `import-batch` 命令
- 实现 `export` 命令（导出到文件夹）
- 实现 `delete` 命令

#### Checks

- [x] C9 验证 skill list 命令
  - Verifies: `specs/skill-cli-commands/spec.md` / Requirement "Skill list 命令" / Scenario "列出所有 skills"
  - Command: `edera skill list`
  - Expect: 显示所有 skills

- [x] C10 验证 skill import-dir 命令
  - Verifies: `specs/skill-cli-commands/spec.md` / Requirement "Skill import-dir 命令" / Scenario "导入单个 skill 文件夹"
  - Command: `edera skill import-dir test-skills/my-skill/`
  - Expect: 导入成功

- [x] C11 验证 skill import-batch 命令
  - Verifies: `specs/skill-cli-commands/spec.md` / Requirement "Skill import-batch 命令" / Scenario "批量导入多个 skill 文件夹"
  - Command: `edera skill import-batch test-skills/`
  - Expect: 批量导入成功

### Task 6: 实现 ReloadSkills RPC

**Goal**: 实现 skill reload API。

**Files**:
- Modify: `proto/edera.proto`
- Modify: `packages/core/src/edera_core/grpc_config_service.py`
- Test: `packages/core/tests/test_skill_reload.py`

**Requirements**:
- 添加 `ReloadSkills` RPC 定义
- 实现从数据库重新加载 skills
- 记录 reload 日志

#### Checks

- [x] C12 验证 reload API
  - Verifies: `specs/skill-dynamic-generation/spec.md` / Requirement "Agent 执行时生成 skill 文件" / Scenario "生成 skill 文件夹到 session 目录"
  - Command: `pytest packages/core/tests/test_skill_reload.py::test_reload_skills -v`
  - Expect: Reload 后新 Agent 使用新 skills

### Task 7: 移除文件系统加载逻辑

**Goal**: 移除从 `config/skills/` 加载的代码，添加 Web Console 多文件限制提示。

**Files**:
- Modify: `packages/core/src/edera_core/config/loader.py`
- Modify: `apps/web-console/src/features/skills/` (添加多文件 skill 限制提示)
- Test: `packages/core/tests/test_config_loader.py`

**Requirements**:
- 移除 `load_skill_configs()` 函数
- 从数据库加载 skills
- Web Console 检测多文件 skill（config_body.files.length > 1）时显示只读模式，提示使用 CLI

#### Checks

- [x] C13 验证不再读取文件系统
  - Verifies: `specs/skill-dynamic-generation/spec.md` / Requirement "Agent 执行时生成 skill 文件" / Scenario "生成 skill 文件夹到 session 目录"
  - Evidence: `packages/core/src/edera_core/config/loader.py`
  - Expect: 移除 `load_skill_configs()` 调用

- [x] C14 验证 Web Console 多文件限制
  - Verifies: Web Console 正确处理多文件 skill
  - Manual: 打开 Web Console skill 管理页面，查看多文件 skill 显示只读提示
  - Expect: 多文件 skill 显示提示："此 skill 包含多个文件，请使用 CLI 管理"
