## ADDED Requirements

### Requirement: Session_dir 字段
`DagNodeInstance.config` SHALL 支持 `session_dir` 字段（可选字符串），控制 LLM 节点的 session 存储位置。

#### Scenario: 添加 session_dir 配置
- **WHEN** 用户在 Inspector 中为 LLM 节点实例设置 `session_dir: "sandbox:llm-analyze:latest"`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: Session_dir 校验
- **WHEN** 用户设置 `session_dir` 为非法格式（如包含非法字符）
- **THEN** 系统 SHALL 拒绝保存并提示格式错误

### Requirement: Tools 字段
`DagNodeInstance.config` SHALL 支持 `tools` 字段（可选字符串数组），覆盖类型层的默认 tools 配置。

#### Scenario: 添加 tools 配置
- **WHEN** 用户在 Inspector 中为 LLM 节点实例设置 `tools: [bash, read, edit, write]`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: Tools 白名单校验
- **WHEN** 用户设置 `tools` 包含非法工具名（不在 pi 支持的工具列表中）
- **THEN** 系统 SHALL 拒绝保存并提示非法工具名

### Requirement: Model 字段移至实例层
`model` 字段 SHALL 从 `NodeConfig`（类型层）移至 `DagNodeInstance.config`（实例层）。

#### Scenario: 实例层 model 配置
- **WHEN** 用户在 Inspector 中为 LLM 节点实例设置 `model: "hf-share/deepseek-v4-flash"`
- **THEN** 系统 SHALL 保存到 DAG YAML 的实例 `config` 中

#### Scenario: 类型层不再包含 model
- **WHEN** 系统加载 `NodeConfig` 定义
- **THEN** 系统 SHALL 不期望 `model` 字段存在于类型层配置中

#### Scenario: 实例未设置 model
- **WHEN** 实例 `config` 中未设置 `model` 字段
- **THEN** executor SHALL 返回错误 "model not configured for instance"

### Requirement: 类型层 tools 默认值
`NodeConfig` SHALL 支持 `tools` 字段（可选字符串数组），作为该类型所有实例的默认工具集。

#### Scenario: 类型层定义默认 tools
- **WHEN** `NodeConfig` 定义 `tools: [bash]`
- **THEN** 该类型的所有实例默认继承 `tools: [bash]`，除非实例层覆盖

#### Scenario: 类型层未定义 tools
- **WHEN** `NodeConfig` 未定义 `tools` 字段
- **THEN** 实例默认 `tools: []`（无工具，等同 `--no-tools`）
