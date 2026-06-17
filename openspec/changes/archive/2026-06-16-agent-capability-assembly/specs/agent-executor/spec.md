## MODIFIED Requirements

### Requirement: Pi CLI subprocess 配置
Agent 节点执行时，系统 SHALL 构造 pi CLI 命令，包含 `--session-dir`、`--model` 参数。当目标会话已有登记的 session id 时，命令 SHALL 包含 `--session <session-id>` 精确续接该会话；无登记时不传，由 pi 创建新会话。MUST NOT 依赖 `--continue` 的目录扫描式自动续接。命令 SHALL 恒定包含 `--no-skills`（关闭 pi 自身的 skills 自动发现）与 `--no-context-files`（关闭 workdir 中 AGENTS.md/CLAUDE.md 的自动发现），使 agent 行为完全由 Edera 配置决定。

#### Scenario: 首次执行不带 session 参数
- **WHEN** agent 节点执行时其 session 组在当前目标会话中无登记的 session id
- **THEN** pi 命令 SHALL 不包含 `--session` 参数，pi 创建新会话

#### Scenario: 续接执行精确指定会话
- **WHEN** agent 节点执行时目标会话已有登记的 session id `S`
- **THEN** pi 命令 SHALL 包含 `--session S`

#### Scenario: 恒定关闭 pi 自动发现
- **WHEN** 任意 agent 节点执行
- **THEN** pi 命令 SHALL 包含 `--no-skills` 与 `--no-context-files`，禁止 pi 从工作目录或默认路径自动加载 skills 与 context 文件

## ADDED Requirements

### Requirement: Skills DB-SoT 物化与复用
系统 SHALL 以数据库 `skills` 表为 skills 的唯一源（single source of truth），并将其物化为固定目录 `skills_dir`（默认 `data/skills`，与 handlers 目录对称）下的 `{skills_dir}/{skill_name}/` 子目录。当 skill 经任何 CRUD 路径变更时，系统 SHALL 通过单一汇聚点（skill 的 upsert 与 delete）刷新该 skill 的物化目录。Agent 节点执行时 SHALL 通过 `--skill {skills_dir}/{skill_name}` 逐个引用本节点声明的技能目录。

#### Scenario: skill 变更刷新物化目录
- **WHEN** 通过任意路径（web API、gRPC、CLI）upsert 或 delete 名为 `foo` 的 skill
- **THEN** 系统 SHALL 在 skill 的 upsert/delete 单一汇聚点刷新 `data/skills/foo/` 的物化内容（删除时移除该目录）

#### Scenario: agent 引用物化技能目录
- **WHEN** agent 节点声明了技能 `foo` 且 `data/skills/foo/` 已物化
- **THEN** pi 命令 SHALL 包含 `--skill {skills_dir}/foo`，pi 从该目录加载技能

#### Scenario: 声明的技能未物化
- **WHEN** agent 节点声明了技能 `foo`，但数据库与 `data/skills/` 中均不存在
- **THEN** 节点执行 SHALL 返回失败，错误信息指明缺失的技能名

### Requirement: Per-node 能力装配
Agent 节点执行时，系统 SHALL 仅装配该节点自身 `AgentNodeConfig.skills` 声明的技能，MUST NOT 装配同一 DAG 或 session 中其他节点声明的技能。System prompt SHALL 按双入口装配：内联 `system_prompt` 字段非空时传递 `--system-prompt <text>`；`system_prompt_file` 字段非空时传递 `--append-system-prompt <file>`，由 pi 在执行时现读文件（磁盘修改即时生效）。

#### Scenario: 仅装配本节点声明的技能
- **WHEN** 同一 session 中节点 A 声明 `skills: [foo]`、节点 B 声明 `skills: [bar]`
- **THEN** 节点 A 执行时 pi 命令 SHALL 仅包含 `--skill {dir}/foo`，MUST NOT 包含 `--skill {dir}/bar`

#### Scenario: 内联 system prompt 装配
- **WHEN** agent 节点配置了非空的内联 `system_prompt` 文本
- **THEN** pi 命令 SHALL 包含 `--system-prompt <该文本>`

#### Scenario: 文件型 system prompt 执行时现读
- **WHEN** agent 节点配置了 `system_prompt_file` 指向一个文件
- **THEN** pi 命令 SHALL 包含 `--append-system-prompt <该文件路径>`
- **THEN** 该文件在执行后被修改，下一次执行 SHALL 反映新内容（pi 执行时现读）

### Requirement: Agent tools 白名单
Agent 节点 SHALL 通过 `AgentNodeConfig.tools` 字段声明允许的工具白名单，系统 SHALL 据此生成 pi 的 `--tools <逗号分隔列表>` 参数。当 `tools` 为空列表或未配置时，系统 SHALL 传递 `--no-tools`，即该 agent 不启用任何工具。agent 节点 MUST NOT 回退到 pi 的默认全工具集。`tools` 字段 SHALL 仅存在于 `AgentNodeConfig`，function 节点 MUST NOT 携带该字段。

#### Scenario: 类型层默认 tools
- **WHEN** `AgentNodeConfig` 定义 `tools: [bash]`，实例未覆盖
- **THEN** executor SHALL 向 pi 传递 `--tools bash`

#### Scenario: 实例层覆盖 tools
- **WHEN** `AgentNodeConfig` 定义 `tools: [bash]`，实例配置 `tools: [bash, read, edit, write]`
- **THEN** executor SHALL 使用实例配置，向 pi 传递 `--tools bash,read,edit,write`

#### Scenario: 空 tools 列表禁用全部工具
- **WHEN** agent 节点的 `tools` 为空列表或未配置
- **THEN** executor SHALL 向 pi 传递 `--no-tools`

#### Scenario: function 节点不携带 tools 字段
- **WHEN** 系统加载 function 类型的节点类型定义
- **THEN** 该节点配置 MUST NOT 包含 `tools` 字段
