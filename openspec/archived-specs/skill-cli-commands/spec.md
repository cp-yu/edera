# skill-cli-commands Specification

## Purpose
此规约记录变更 skills-to-database 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Skill list 命令
系统 SHALL 提供 `edera skill list` 命令列出所有 skills。

#### Scenario: 列出所有 skills
- **WHEN** 用户执行 `edera skill list`
- **THEN** 系统 SHALL 显示所有 skills 的 name、display_name、description

### Requirement: Skill show 命令
系统 SHALL 提供 `edera skill show` 命令显示单个 skill 详情。

#### Scenario: 显示 skill 详情
- **WHEN** 用户执行 `edera skill show SKILL_NAME`
- **THEN** 系统 SHALL 显示该 skill 的所有字段，包括文件列表

### Requirement: Skill create 命令
系统 SHALL 提供 `edera skill create` 命令创建 skill。

#### Scenario: 从文件夹创建 skill
- **WHEN** 用户执行 `edera skill create --from-dir ./my-skill/`
- **THEN** 系统 SHALL 扫描文件夹，读取所有文件并创建 skill
- **THEN** 系统 SHALL 验证 SKILL.md 存在

### Requirement: Skill update 命令
系统 SHALL 提供 `edera skill update` 命令更新 skill。

#### Scenario: 从文件夹更新 skill
- **WHEN** 用户执行 `edera skill update SKILL_NAME --from-dir ./my-skill/`
- **THEN** 系统 SHALL 读取文件夹内容并更新数据库

### Requirement: Skill import-dir 命令
系统 SHALL 提供 `edera skill import-dir` 命令导入单个 skill 文件夹。

#### Scenario: 导入单个 skill 文件夹
- **WHEN** 用户执行 `edera skill import-dir ./skills/openspec-impact-sweeper/`
- **THEN** 系统 SHALL 导入该文件夹为一个 skill

### Requirement: Skill import-batch 命令
系统 SHALL 提供 `edera skill import-batch` 命令批量导入。

#### Scenario: 批量导入多个 skill 文件夹
- **WHEN** 用户执行 `edera skill import-batch ./skills/`
- **THEN** 系统 SHALL 扫描目录下所有包含 SKILL.md 的子文件夹
- **THEN** 系统 SHALL 导入每个识别到的 skill 文件夹

### Requirement: Skill export 命令
系统 SHALL 提供 `edera skill export` 命令导出。

#### Scenario: 导出单个 skill 到文件夹
- **WHEN** 用户执行 `edera skill export SKILL_NAME -o ./output/`
- **THEN** 系统 SHALL 在 `./output/SKILL_NAME/` 创建文件夹
- **THEN** 系统 SHALL 生成所有文件，保持原始目录结构

### Requirement: Skill delete 命令
系统 SHALL 提供 `edera skill delete` 命令删除 skill。

#### Scenario: 删除 skill
- **WHEN** 用户执行 `edera skill delete SKILL_NAME`
- **THEN** 系统 SHALL 从数据库删除该 skill

