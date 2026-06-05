## ADDED Requirements

### Requirement: Agent 执行时生成 skill 文件
系统 SHALL 在 Agent 启动前，从数据库查询 skills 并生成完整的 skill 文件夹到临时目录。

#### Scenario: 生成 skill 文件夹到 session 目录
- **WHEN** Agent session 启动
- **THEN** 系统 SHALL 查询数据库所有 skills
- **THEN** 系统 SHALL 为每个 skill 在 `{session_dir}/skills/{skill_name}/` 创建文件夹
- **THEN** 系统 SHALL 从 config_body.files 数组遍历，生成所有文件
- **THEN** 系统 SHALL 根据 file.path 创建子目录（如 "prompts/main.txt" 需先创建 "prompts" 目录）

#### Scenario: Skill 文件内容与数据库一致
- **WHEN** 生成 skill 文件
- **THEN** 每个文件的内容 SHALL 与数据库中 config_body.files[i].content 完全一致
- **THEN** 文件路径 SHALL 与 config_body.files[i].path 一致

#### Scenario: 多个 Agent 并发执行不冲突
- **WHEN** 两个 Agent session 同时启动
- **THEN** 每个 session SHALL 使用独立的 skills 目录（`{session_dir}/skills/`）
- **THEN** 文件生成不冲突

#### Scenario: 多文件 skill 结构完整还原
- **WHEN** Skill 包含多个文件（如 SKILL.md, prompts/main.txt, scripts/helper.py）
- **THEN** 系统 SHALL 创建完整的文件夹结构
- **THEN** 所有文件 SHALL 按原始路径生成

### Requirement: Session 结束后保留临时文件
系统 SHALL 在 Agent session 结束后保留 skill 临时文件，用于调试。

#### Scenario: Session 结束后文件仍存在
- **WHEN** Agent session 执行完成
- **THEN** `{session_dir}/skills/` 目录和所有文件 SHALL 保留
- **THEN** 用户可查看这些文件用于调试
