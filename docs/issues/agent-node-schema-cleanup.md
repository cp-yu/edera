# Agent Node Schema 清理

## 背景

当前 `AgentNodeConfig` 和 `FunctionNodeConfig` 都继承自 `NodeConfigBase`，各自声明专属字段。但存在字段冗余和不一致的问题。

## 问题

### 1. `parameters_schema` 冗余

`AgentNodeConfig` 定义了 `parameters_schema`，但 `_execute_agent()` 全程不读取该字段。它只在 Function 节点的 handler 路径中被消费。

```python
# schema.py
class AgentNodeConfig(NodeConfigBase):
    ...
    parameters_schema: dict[str, Any] = Field(default_factory=dict)  # ← 无人消费
```

尽管 `parameters_schema` 通过 `NodeConfigBase.model_validate()` 的 validator `_json_like_parameters_schema` 做了校验，但校验通过后值被丢弃。

**结论**：`parameters_schema` 应从 `AgentNodeConfig` 移除。`FunctionNodeConfig` 保留不动。

### 2. `input_type` 未传入 Agent 上下文

`input_type` 在 `NodeConfigBase` 中定义，Function 节点通过 handler 上下文消费。但 Agent 节点执行时 `input_type` 从未被传入 Agent（pi 子进程）的运行时上下文中。

Agent 节点的输入不局限于文本。多模态模型可消费图片、音频等，列表/复合类型也需要 Agent 知晓输入格式以便正确处理 payload。

**目标**：将 `input_type` 传入 `runtime_context`，Agent 据此决定如何处理 payload：

| input_type | Agent 行为 |
|------------|-----------|
| `Text` | payload 字符串直接放入 prompt（现有行为） |
| `Image` | runtime_context 给引用路径/URL，Agent 用 read tool 读取 |
| `Audio` | 同上 |
| `List[RawItem]` / 复合类型 | 给摘要 + Edera CLI 命令，Agent 自行拉取 |

涉及改动点：

1. `_agent_runtime_context()` — 增加 `input_type` 字段
2. `_agent_prompt()` — 根据 `input_type` 调整 prompt 生成策略

### 3. `parameters` 确认不出现在 Agent 侧

`AgentNodeConfig` 当前没有 `parameters` 字段，符合预期。Agent 的参数通过 `system_prompt`、`system_prompt_file`、`skills` 等机制传递，不需要 Function 节点风格的 `parameters` 字典。

此项无需改动，仅确认。

## 改动范围

| 文件 | 改动 |
|------|------|
| `packages/core/src/edera_core/config/schema.py` | `AgentNodeConfig`: 移除 `parameters_schema` 字段及其 validator |
| `packages/core/src/edera_core/node/executor.py` | `_agent_runtime_context()`: 新增 `input_type` 字段；`_agent_prompt()`: 根据 `input_type` 调整策略 |

## 不在本 Issue 范围内

- Agent 侧 `input_type` 的具体 payload 处理策略（如 `_summarize()` 函数、Edera CLI 拉取协议）—— 将在实现阶段详细设计
- Function 节点的任何改动
