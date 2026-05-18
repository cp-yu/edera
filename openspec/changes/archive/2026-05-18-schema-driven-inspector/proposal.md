## Why

Inspector 当前使用硬编码条件渲染（`if type==='llm'` / `'function'`）展示编辑字段，所有输入均为自由文本。这带来两个问题：每新增节点类型或可配置字段都需要改前端代码；用户无法从可选值中选择（如 model 下拉、skills 多选），只能手动输入，容易出错。Spec（`node-graph-dag-editor` L141-146）已明确要求 `skills（多选）`、`model（下拉）`、`parameters（schema 驱动表单）`，但实现尚未对齐。

## What Changes

- 后端 `NodeConfig` 新增 `parameters_schema` 字段（JSON Schema 格式，与 `SkillConfig` 统一模式）
- 后端 API 返回 node type 时，自动合并顶层可编辑字段（`model`、`skills`、`source_names`、`timeout_seconds`）的 schema 描述 + YAML 中手写的 `parameters_schema`，输出完整的 JSON Schema
- 后端对 `source: "skills"` / `source: "models"` 等动态引用预填充 `enum` 值，前端只需处理标准 JSON Schema
- Inspector 保存时，后端将 schema 覆盖的字段拆回顶层字段 + `config`，运行时代码零改动
- 前端新建 schema 表单渲染器组件，支持 `string`、`string+enum`（下拉）、`integer/number`、`boolean` 四种字段类型
- 前端 Inspector 删除所有硬编码条件字段，保留顶部 `alias` + 只读元信息，其余全部由 schema 驱动渲染
- 值优先级：实例 config > 类型默认值 > schema default；清空字段 = 删除实例覆盖回退默认；只保存差异值

## Capabilities

### New Capabilities

### Modified Capabilities
- `node-type-registry`: 节点类型定义新增 `parameters_schema` 字段；API 返回时自动生成包含顶层字段 + 自定义参数的完整 schema，动态引用预填充 enum
- `node-graph-dag-editor`: Inspector 从硬编码字段切换为 schema 驱动表单渲染；编辑保存采用三级回退 + 差异保存语义

## Impact

- 后端：`schema.py`（`NodeConfig` 加字段）、`routes.py`（schema 合并/拆分逻辑、enum 填充）
- 前端：`Inspector.tsx`（重写为 schema 驱动）、新建 `SchemaForm.tsx` 渲染器、`types.ts`（`NodeType` 加 `parameters_schema`）
- 配置：`config/nodes/*.yaml` 可选添加 `parameters_schema`（非 breaking，默认空）
- 运行时：零改动，顶层字段存储不变
