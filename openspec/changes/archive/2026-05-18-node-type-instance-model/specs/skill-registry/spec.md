## ADDED Requirements

### Requirement: Skill definition schema
系统 SHALL 在 `config/skills/` 目录下注册独立的 skill 定义文件，每个 skill 一个 YAML。

#### Scenario: Load skill definition
- **WHEN** 系统加载 `config/skills/summarize.yaml`
- **THEN** 系统 SHALL 解析以下字段：`name`、`description`、`handler`（指向 `skill_handlers/` 下的 Python 文件）、`parameters_schema`（JSON Schema 格式）

#### Scenario: Skill handler resolution
- **WHEN** skill 定义中 `handler: summarize`
- **THEN** 系统 SHALL 将其解析为 `skill_handlers/summarize.py` 中的执行入口

### Requirement: Skill registry API
系统 SHALL 提供 skill 的 CRUD API。

#### Scenario: List all skills
- **WHEN** 前端请求 `GET /api/graph/skills`
- **THEN** 系统 SHALL 返回所有已注册 skill 的 `name`、`description`、`parameters_schema`

#### Scenario: Create skill
- **WHEN** 前端提交 `POST /api/graph/skills` 包含 name、description、handler 代码、parameters_schema
- **THEN** 系统 SHALL 创建 skill YAML 文件和 handler Python 文件

#### Scenario: Update skill
- **WHEN** 前端提交 `PUT /api/graph/skills/{name}`
- **THEN** 系统 SHALL 更新对应 YAML 和 handler 文件

#### Scenario: Delete skill
- **WHEN** 前端提交 `DELETE /api/graph/skills/{name}`
- **THEN** 系统 SHALL 删除对应 YAML 和 handler 文件

### Requirement: Skill handler isolation
Skill handler SHALL 存放在 `skill_handlers/` 目录，与 Function 节点的 `handlers/` 目录分离。

#### Scenario: Directory separation
- **WHEN** 系统加载 skill handler 和 function handler
- **THEN** 系统 SHALL 分别从 `skill_handlers/` 和 `handlers/` 加载，两者互不干扰
