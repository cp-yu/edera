## ADDED Requirements

### Requirement: Skills 存储到数据库
系统 SHALL 将所有 skills 存储到 `skills` 数据库表中，支持多文件结构。

#### Scenario: 创建 skill
- **WHEN** 用户调用 `create_skill(name="test-skill", files=[{path: "SKILL.md", content: "..."}, ...])`
- **THEN** 系统 SHALL 验证 name 唯一性
- **THEN** 系统 SHALL 验证 files 数组中包含 "SKILL.md" 文件
- **THEN** 系统 SHALL 序列化 files 为 JSON 存储到 `config_body` 字段，格式为 `{files: [{path, content}, ...]}`

#### Scenario: 查询所有 skills
- **WHEN** 系统启动时加载 skills
- **THEN** 系统 SHALL 查询 `skills` 表所有记录
- **THEN** 系统 SHALL 反序列化 config_body.files 为 Python list

#### Scenario: 更新 skill
- **WHEN** 用户调用 `update_skill(name="test-skill", files=[...])`
- **THEN** 系统 SHALL 更新 config_body 和 updated_at 字段

#### Scenario: 删除 skill
- **WHEN** 用户调用 `delete_skill(name="test-skill")`
- **THEN** 系统 SHALL 从数据库删除该 skill

### Requirement: 从文件夹导入 skills
系统 SHALL 支持从文件夹批量导入 skills。

#### Scenario: 导入单个 skill 文件夹
- **WHEN** 用户调用 `import_skill_dir("skills/openspec-impact-sweeper/")`
- **THEN** 系统 SHALL 扫描文件夹下所有文件
- **THEN** 系统 SHALL 验证 SKILL.md 存在
- **THEN** 系统 SHALL 读取所有文件内容，构建 files 数组
- **THEN** 系统 SHALL 创建或更新 skill（skill name 从文件夹名提取）

#### Scenario: 批量导入多个 skill 文件夹
- **WHEN** 用户调用 `import_skills_batch("skills/")`
- **THEN** 系统 SHALL 遍历目录下所有子文件夹
- **THEN** 系统 SHALL 识别包含 SKILL.md 的文件夹为一个 skill
- **THEN** 系统 SHALL 导入每个 skill 文件夹

### Requirement: 导出 skills 到文件夹
系统 SHALL 支持将 skills 导出为文件夹。

#### Scenario: 导出单个 skill
- **WHEN** 用户调用 `export_skill(name="test-skill", output_dir="output/")`
- **THEN** 系统 SHALL 创建 `output/test-skill/` 目录
- **THEN** 系统 SHALL 从 config_body.files 遍历，生成所有文件
- **THEN** 系统 SHALL 保持原始文件路径结构（创建子目录）
