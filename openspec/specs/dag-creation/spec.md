---
capabilities:
  - cap.web.dag-creation
---
# dag-creation Specification

## Purpose
此规约记录变更 dag-observability-controllability 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: DAG 创建 API

系统 SHALL 提供 `POST /api/graph/dag` 端点，创建新的空 DAG 配置文件。

#### Scenario: 创建新 DAG 成功

- **WHEN** 用户调用 `POST /api/graph/dag` body `{ "name": "weekly-report" }`
- **THEN** 系统 MUST 创建 `config/dags/weekly-report.yaml`（内容为 `{ name: "weekly-report", nodes: [], edges: [] }`），返回 201 和空 DAG 结构

#### Scenario: DAG 名称已存在

- **WHEN** 用户提交的 name 与已有 DAG 配置文件同名
- **THEN** 系统 MUST 返回 409 错误，包含 `conflict` 错误类型

#### Scenario: DAG 名称不合法

- **WHEN** 用户提交的 name 包含非 kebab-case 字符（如空格、大写、特殊符号）
- **THEN** 系统 MUST 返回 400 错误，包含 `config_error` 错误类型

### Requirement: DAG 创建前端入口

系统 SHALL 在 DAG dropdown 中提供 "+ 新建 DAG" 选项，点击后弹出 dialog 输入名称并调用创建 API。

#### Scenario: 从 dropdown 创建 DAG

- **WHEN** 用户点击 DAG dropdown 中的 "+ 新建 DAG" 选项
- **THEN** 系统 SHALL 弹出 dialog，包含名称输入框和确认/取消按钮

#### Scenario: 创建成功后切换画布

- **WHEN** 用户在 dialog 中输入合法名称并确认
- **THEN** 系统 MUST 调用创建 API，成功后自动切换到新 DAG 的空画布，dropdown 刷新显示新 DAG

