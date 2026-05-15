## ADDED Requirements

### Requirement: Structured DAG visual editing
系统 SHALL 在 Web 配置界面对 DAG 配置提供结构化可视化编辑入口，并且该入口 SHALL 仅在当前配置类型为 `dag` 时展示。

#### Scenario: View DAG editor for dag config
- **WHEN** 用户打开 `/config?kind=dag&name=default`
- **THEN** 系统 SHALL 展示当前 DAG 的节点、边、`fan_in`、`fan_out` 和可视化预览

#### Scenario: Hide DAG editor for non-dag config
- **WHEN** 用户打开非 `dag` 类型的配置编辑页面
- **THEN** 系统 SHALL 不展示 DAG 结构化编辑入口

### Requirement: Structured DAG save
系统 SHALL 支持通过结构化 Web 表单保存 DAG 节点和边，并写回现有 `config/dags/*.yaml` 文件。

#### Scenario: Save valid structured DAG
- **WHEN** 用户提交合法的 DAG 节点、边和 fan flags
- **THEN** 系统 SHALL 将其序列化为现有 DAG YAML 格式并保存到对应 `config/dags/*.yaml`

#### Scenario: Preserve DAG fan flags
- **WHEN** 用户在结构化 DAG 表单中切换 `fan_in` 或 `fan_out`
- **THEN** 系统 SHALL 将对应 flag 写入保存后的 DAG YAML

### Requirement: Structured DAG validation semantics
系统 MUST 复用运行时配置编辑的保存前校验和原子写入语义保存结构化 DAG，非法 DAG MUST 被拒绝且不得写入目标文件。

#### Scenario: Reject cyclic structured DAG
- **WHEN** 用户通过结构化 DAG 表单提交形成环的 DAG
- **THEN** 系统 MUST 返回 DAG 校验错误并保持原 DAG 文件内容不变

#### Scenario: Reject unknown DAG node reference
- **WHEN** 用户通过结构化 DAG 表单提交引用不存在 Node 的 DAG
- **THEN** 系统 MUST 返回 DAG 校验错误并保持原 DAG 文件内容不变

#### Scenario: Reject DAG I/O mismatch
- **WHEN** 用户通过结构化 DAG 表单提交 I/O 类型不匹配的边
- **THEN** 系统 MUST 返回 DAG 校验错误并保持原 DAG 文件内容不变

### Requirement: DAG YAML fallback editing
系统 SHALL 保留 DAG YAML 原文编辑入口，作为结构化编辑之外的高级编辑和无障碍兜底。

#### Scenario: Save DAG through raw YAML editor
- **WHEN** 用户在 DAG 配置页使用 YAML 原文编辑表单保存合法内容
- **THEN** 系统 SHALL 继续通过通用配置保存路径写入 DAG 文件

#### Scenario: Edit DAG without JavaScript
- **WHEN** 浏览器无法运行 DAG 结构化编辑脚本
- **THEN** 用户 SHALL 仍能通过 YAML 原文编辑入口查看并保存 DAG 配置
