---
capabilities:
  - cap.core.dag-input-parameters
---
# dag-input-parameters Specification

## Purpose
定义 DAG 输入参数声明、Source 节点 Input Binding、运行时参数传递、Web Console 输入表单等能力。
## Requirements
### Requirement: DAG 输入参数声明
DAG 配置 SHALL 支持 `inputs` 字段，声明该 DAG 接受的外部输入参数。每个 input SHALL 包含 `name`、`type`、`required` 字段。

#### Scenario: DAG 声明输入参数
- **WHEN** DAG 配置包含 `inputs: [{name: ticker, type: string, required: false}]`
- **THEN** 系统 SHALL 识别该 DAG 接受名为 `ticker` 的可选字符串输入

### Requirement: Source 节点 Input Binding
Source 节点实例配置 SHALL 支持 `input_binding` 字段，绑定到 DAG 的某个 input 参数。当 DAG 运行时传入该参数值时，绑定的 source 节点 SHALL 跳过正常拉取，直接使用传入值。

#### Scenario: Source 绑定 DAG input
- **WHEN** source 节点配置 `input_binding: ticker`
- **THEN** 该节点 SHALL 绑定到 DAG 的 `ticker` input

#### Scenario: 有 input 值时跳过拉取
- **WHEN** DAG 运行时传入 `ticker=00100.HK`，且某 source 节点绑定了 `ticker`
- **THEN** 该 source 节点 SHALL 跳过 `source_names` 拉取，直接使用 `00100.HK` 作为输出

#### Scenario: 无 input 值时正常拉取
- **WHEN** DAG 运行时未传入 `ticker` 参数，且某 source 节点绑定了 `ticker`
- **THEN** 该 source 节点 SHALL 从 `source_names` 正常拉取数据

### Requirement: 运行时参数传递
DAG 触发 API SHALL 支持 `inputs` 参数，允许外部传入 DAG 声明的输入参数。

#### Scenario: CLI 传递输入参数
- **WHEN** 用户执行 `edera dag run my-dag --input ticker=00100.HK`
- **THEN** 系统 SHALL 将 `{ticker: "00100.HK"}` 传递给 DAG 运行时

#### Scenario: HTTP API 传递输入参数
- **WHEN** 客户端 POST `/api/dags/my-dag/run` 并携带 `{"inputs": {"ticker": "00100.HK"}}`
- **THEN** 系统 SHALL 将 inputs 传递给 DAG 运行时

### Requirement: Web Console 输入表单
Web Console 的 DAG 触发界面 SHALL 根据 DAG 的 `inputs` 声明动态渲染输入表单。

#### Scenario: 根据 inputs 渲染表单
- **WHEN** 用户在 Web Console 点击触发 DAG
- **THEN** 界面 SHALL 根据 DAG 的 `inputs` 声明渲染对应的输入字段

### Requirement: Sub-DAG 输入接口
当 DAG 作为 dag 节点嵌套执行时，其 `inputs` 声明 SHALL 作为该节点的输入接口。父 DAG 通过 `input_mapping` 将上游输出映射到子 DAG 的 inputs。

#### Scenario: Sub-DAG inputs 作为接口
- **WHEN** dag 节点引用的目标 DAG 声明了 `inputs: [{name: data}]`
- **THEN** 该 dag 节点 SHALL 接受 `input_mapping: {data: upstream_output}` 映射上游输出到子 DAG 的 `data` input
