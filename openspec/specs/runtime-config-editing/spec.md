---
capabilities:
  - cap.config.runtime-config-editing
---
# runtime-config-editing Specification

## Purpose

定义运行时配置编辑能力，包括读取、展示、校验、原子保存 config 与 skills 文档，并保持运行中周期使用启动时配置快照。
## Requirements
### Requirement: Read runtime configuration

系统 SHALL 从 DB-backed core Entity、system config 和 skill 文档读取可编辑配置，并通过 WebUI 展示。YAML 文件仅作为 import/export/template 格式。

#### Scenario: View system config

- **WHEN** 用户打开配置页面
- **THEN** 系统 SHALL 直接展示 System 配置编辑器（TOML 文本），无 tab 切换

#### Scenario: View node and dag config

- **WHEN** 用户打开 Node 或 DAG 配置页面
- **THEN** 系统 SHALL 展示对应 YAML 内容或等价结构化字段

### Requirement: Validate before save

系统 MUST 在写入配置文件前校验配置内容。

#### Scenario: Invalid system config rejected

- **WHEN** 用户提交不符合 SystemConfig schema 的配置
- **THEN** 系统 MUST 拒绝保存并返回校验错误

#### Scenario: Invalid dag rejected

- **WHEN** 用户提交引用不存在 Node 或形成环的 DAG 配置
- **THEN** 系统 MUST 拒绝保存并返回 DAG 校验错误

#### Scenario: Invalid node rejected

- **WHEN** 用户提交缺少 skill 或 I/O 类型不匹配的 Node 配置
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Atomic config save
系统 SHALL 以原子方式保存配置文件，避免半写入状态。

#### Scenario: Successful config save
- **WHEN** 用户提交合法配置
- **THEN** 系统 SHALL 写入目标配置文件，并保证写入过程中不会留下部分内容

### Requirement: Running run uses config snapshot
系统 SHALL 保证已经开始的管道周期使用启动时加载的配置快照。

#### Scenario: Edit config during active run
- **WHEN** 用户在管道运行中保存新配置
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新配置只影响后续运行

### Requirement: Skill document editing
系统 SHALL 支持查看和编辑 `skills/*` 下的 Skill 文档类文件，并限制编辑范围在项目 `skills/` 目录内。

#### Scenario: Save skill workflow
- **WHEN** 用户编辑合法 Skill 文档并保存
- **THEN** 系统 SHALL 写入对应 `skills/<name>/` 下的文件

#### Scenario: Reject path traversal
- **WHEN** 用户请求编辑 `skills/` 目录外的路径
- **THEN** 系统 MUST 拒绝该请求

### Requirement: Analysis parameter tuning entry
系统 SHALL 在 Web 配置界面提供分析参数调优入口，帮助用户定位会影响分析链结果的运行时配置。

#### Scenario: View analysis tuning entry
- **WHEN** 用户打开 Web 配置界面
- **THEN** 系统 SHALL 提供分析参数调优入口，并展示可调参数对应的配置来源

#### Scenario: Preserve generic config editing
- **WHEN** 用户使用通用配置编辑入口
- **THEN** 系统 SHALL 继续支持编辑 `system`、`portfolio`、`node`、`dag` 和 `skill` 配置

### Requirement: Bounded analysis parameters
系统 MUST 将第一版分析参数调优限制在 schema 明确允许的配置字段内，包括 `NodeConfig.timeout_seconds`、`NodeConfig.model`、采集节点 `source_names`、`SystemConfig.llm_timeout_seconds`，以及节点 YAML 中的 `parameters` mapping。

#### Scenario: Show supported node parameters
- **WHEN** 用户查看分析参数调优入口
- **THEN** 系统 SHALL 展示 reader/advisor/briefing 相关节点中可编辑的 `model`、`timeout_seconds` 和 `parameters` 字段

#### Scenario: Show analysis input source parameters
- **WHEN** 用户查看分析参数调优入口
- **THEN** 系统 SHALL 展示采集节点的 `source_names`，用于调整后续分析输入范围

#### Scenario: Reject unsupported analysis parameter
- **WHEN** 用户提交 schema 未允许的分析参数字段
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Node private tuning parameters
系统 SHALL 支持在 Node YAML 中配置 `parameters` mapping，用于节点私有、非凭据、可序列化的分析调优参数。

#### Scenario: Save node parameters
- **WHEN** 用户为 reader、advisor 或 briefing 节点提交合法 `parameters` mapping
- **THEN** 系统 SHALL 保存对应 Node YAML，并让新参数仅影响后续运行

#### Scenario: Reject invalid node parameters
- **WHEN** 用户提交不可序列化或不符合 schema 的 `parameters` 内容
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Analysis tuning save semantics
系统 SHALL 复用运行时配置编辑的保存前校验、原子写入和运行中配置快照语义保存分析参数。

#### Scenario: Save valid analysis tuning
- **WHEN** 用户在分析参数调优入口提交合法参数
- **THEN** 系统 SHALL 原子写入对应配置文件，并返回保存成功状态

#### Scenario: Active run keeps previous parameters
- **WHEN** 用户在管道运行中保存新的分析参数
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新参数只影响后续运行

### Requirement: Analysis tuning rollback boundary
系统 SHALL 在第一版明确分析参数调优不提供内置版本历史或一键回滚。

#### Scenario: Save without internal version history
- **WHEN** 用户保存分析参数
- **THEN** 系统 SHALL 不创建数据库参数版本记录，并 SHALL 保持配置文件为唯一运行时参数来源

### Requirement: Node Graph as primary DAG editor
系统 SHALL 将 Node Graph 作为 DAG 可视化编辑的主要 Web 入口，同时保留 YAML 兜底编辑。

#### Scenario: Navigate to primary DAG graph editor
- **WHEN** 用户从配置页进入 DAG 编辑
- **THEN** 系统 SHALL 优先打开 Node Graph DAG 编辑界面，而不是仅展示表格编辑器

#### Scenario: Continue raw DAG editing
- **WHEN** 用户选择高级或兜底编辑
- **THEN** 系统 SHALL 继续提供现有 DAG YAML 编辑能力

### Requirement: Node Graph save uses runtime config semantics
系统 MUST 使用运行时配置编辑的校验、原子写入和运行中配置快照语义保存 Node Graph 产生的 DAG 和 Node 配置。

#### Scenario: Graph DAG save uses existing validation
- **WHEN** Node Graph 保存 DAG
- **THEN** 系统 MUST 通过 `RuntimeConfigEditor.save("dag", ...)` 和 `load_graph()` 校验后写入

#### Scenario: Inspector node save uses existing validation
- **WHEN** Inspector 保存 Node 配置
- **THEN** 系统 MUST 通过 `RuntimeConfigEditor.save("node", ...)` 校验后写入

#### Scenario: Active run keeps previous graph config
- **WHEN** 用户在管道运行中通过 Node Graph 保存 DAG 或 Node 配置
- **THEN** 系统 SHALL 让当前运行继续使用启动时配置，并让新配置只影响后续运行

### Requirement: Read system config via dedicated endpoint
系统 SHALL 提供 `GET /api/config/system` 端点，返回 system 配置文件的原始 TOML 文本内容。

#### Scenario: Read system config successfully
- **WHEN** 前端请求 `GET /api/config/system`
- **THEN** 系统 SHALL 返回 `{ "content": "<toml text>" }` 格式的响应

#### Scenario: System config file missing
- **WHEN** `config/system.toml` 文件不存在
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: Read entities config via dedicated endpoint

系统 SHALL 提供 `GET /api/config/entities` 端点，以 YAML import/export 格式返回 DB-backed Entity Store 中的 entities 内容。

#### Scenario: Read entities config successfully

- **WHEN** 前端请求 `GET /api/config/entities`
- **THEN** 系统 SHALL 返回 `{ "content": "<yaml text>" }` 格式的响应

#### Scenario: Entities config file missing

- **WHEN** DB-backed Entity Store 中无对应 entities
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: Read entity-relations config via dedicated endpoint

系统 SHALL 提供 `GET /api/config/entity-relations` 端点，以 YAML import/export 格式返回 DB-backed relation Entity 内容。

#### Scenario: Read entity-relations config successfully

- **WHEN** 前端请求 `GET /api/config/entity-relations`
- **THEN** 系统 SHALL 返回 `{ "content": "<yaml text>" }` 格式的响应

#### Scenario: Entity-relations config file missing

- **WHEN** DB-backed relation Entity Store 中无对应 relations
- **THEN** 系统 MUST 返回 404 错误，包含 `not_found` 错误类型

### Requirement: Save entities config

系统 SHALL 支持通过 `POST /api/config/entities` 保存 entities 配置，并验证实体类型和 schema。

#### Scenario: Save valid entities config

- **WHEN** 用户提交符合 entities schema 的配置
- **THEN** 系统 SHALL 原子写入 DB-backed Entity Store，并返回保存成功状态

#### Scenario: Reject invalid entity type

- **WHEN** 用户提交的实体 `type` 在 DB-backed EntityType 元数据中不存在
- **THEN** 系统 MUST 拒绝保存并返回校验错误 "Unknown entity type: <type>"

#### Scenario: Reject invalid entity attributes

- **WHEN** 用户提交的实体 `attributes` 不符合对应类型的 schema
- **THEN** 系统 MUST 拒绝保存并返回校验错误

### Requirement: Save entity-relations config

系统 SHALL 支持通过 `POST /api/config/entity-relations` 保存 entity-relations 配置，并验证引用的实体存在。

#### Scenario: Save valid entity-relations config

- **WHEN** 用户提交符合 entity-relations schema 的配置
- **THEN** 系统 SHALL 原子写入 DB-backed relation Entity Store，并返回保存成功状态

#### Scenario: Reject relation with non-existent entity

- **WHEN** 用户提交的关系引用不存在的实体
- **THEN** 系统 MUST 拒绝保存并返回校验错误 "Entity not found: <entity_ref>"
