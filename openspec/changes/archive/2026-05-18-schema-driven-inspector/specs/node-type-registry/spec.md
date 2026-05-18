## MODIFIED Requirements

### Requirement: Node type definition schema
系统 SHALL 支持两种节点类型定义格式：LLM 类型和 Function 类型，均通过 YAML 文件在 `config/nodes/` 目录注册。每个节点类型 SHALL 可选声明 `parameters_schema`（JSON Schema 格式）描述 `parameters` 内部自定义字段的类型、默认值和可选值。

#### Scenario: LLM node type definition
- **WHEN** 系统加载 `config/nodes/` 下一个 `type: llm` 的 YAML 文件
- **THEN** 系统 SHALL 解析以下字段：`name`、`type: llm`、`role`、`system_prompt_file`、`skills`（默认启用列表）、`input_type`、`output_type`、`model`（可选）、`parameters`（可选）、`parameters_schema`（可选，JSON Schema 格式）

#### Scenario: Function node type definition
- **WHEN** 系统加载 `config/nodes/` 下一个 `type: function` 的 YAML 文件
- **THEN** 系统 SHALL 解析以下字段：`name`、`type: function`、`role`、`handler`、`input_type`、`output_type`、`source_names`（可选）、`timeout_seconds`（可选）、`parameters`（可选）、`parameters_schema`（可选，JSON Schema 格式）

#### Scenario: Invalid parameters_schema rejected
- **WHEN** 节点 YAML 中 `parameters_schema` 不是合法的 JSON Schema object
- **THEN** 系统 MUST 拒绝加载该节点类型并报告校验错误

### Requirement: Node type API
系统 SHALL 提供节点类型的 CRUD API。

#### Scenario: List all node types
- **WHEN** 前端请求 `GET /api/graph/node-types`
- **THEN** 系统 SHALL 返回所有节点类型定义，包含 `name`、`type`、`role`、`input_type`、`output_type` 及类型特有字段

#### Scenario: Node type response includes complete schema
- **WHEN** 前端请求 `GET /api/graph/node-types` 或 `GET /api/graph/dag/{name}`
- **THEN** 系统 SHALL 在每个节点类型/实例响应中包含 `inspector_schema` 字段，该字段为完整的 JSON Schema，合并了顶层可编辑字段（`model`、`skills`、`source_names`、`timeout_seconds`）的自动生成 schema 和 YAML 中手写的 `parameters_schema`

#### Scenario: LLM node inspector_schema auto-generation
- **WHEN** 后端为 `type: llm` 节点生成 `inspector_schema`
- **THEN** 系统 SHALL 自动包含 `model`（string + enum，enum 从系统可用模型列表填充）、`skills`（array of string，items enum 从已注册 skills 列表填充）、`timeout_seconds`（number）的 schema 描述

#### Scenario: Function node inspector_schema auto-generation
- **WHEN** 后端为 `type: function` 且 `role: source` 节点生成 `inspector_schema`
- **THEN** 系统 SHALL 自动包含 `source_names`（array of string，items enum 从 portfolio sources 列表填充）、`timeout_seconds`（number）的 schema 描述

#### Scenario: Parameters schema merged into inspector_schema
- **WHEN** 节点 YAML 定义了 `parameters_schema` 且其 `properties` 非空
- **THEN** 系统 SHALL 将 `parameters_schema.properties` 中的每个字段合并进 `inspector_schema.properties`，键名加 `param.` 前缀以区分

#### Scenario: Create LLM node type
- **WHEN** 前端提交 `POST /api/graph/node-types` 且 `type: llm`
- **THEN** 系统 SHALL 创建对应 YAML 文件和 prompt 文件，返回新类型定义

#### Scenario: Update node type
- **WHEN** 前端提交 `PUT /api/graph/node-types/{name}`
- **THEN** 系统 SHALL 更新对应 YAML 文件，结构性字段变更 SHALL 触发关联 DAG 实例的兼容性检查

#### Scenario: Delete node type
- **WHEN** 前端提交 `DELETE /api/graph/node-types/{name}` 且该类型在任何 DAG 中无实例引用
- **THEN** 系统 SHALL 删除对应 YAML 文件
