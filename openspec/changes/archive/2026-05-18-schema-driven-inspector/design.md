## Context

Inspector 当前对 LLM / Function 两种节点类型做硬编码条件渲染，所有可编辑字段均为自由文本输入。`SkillConfig` 已有 `parameters_schema`（JSON Schema）先例，但 `NodeConfig` 未跟进。后端 `routes.py:339-354` 已在做 instance config → 顶层字段的合并覆盖。运行时代码直接访问 `node.model`、`node.skills` 等顶层属性。

## Goals / Non-Goals

**Goals:**
- Inspector 展示的所有可编辑字段由 JSON Schema 驱动，前端不含节点类型特定的硬编码逻辑
- `model` 渲染为下拉、`skills` 渲染为多选、`timeout_seconds` 渲染为数字输入
- 动态引用（skills 列表、model 列表）由后端预填充 enum，前端只认标准 JSON Schema
- 顶层字段存储不变，运行时代码零改动

**Non-Goals:**
- 不迁移顶层字段（`model`/`skills`/`source_names`）进 `parameters`（存储层兼容）
- 不支持 `array`、嵌套 `object` 字段类型（第一版）
- 不改动节点类型编辑页面（`NodesPage.tsx`）
- 不支持 schema 内嵌验证规则（`minLength`、`pattern` 等）
- 不提供字段级权限控制

## Decisions

### D1: Schema 来源——混合模式

顶层已知字段（`model`、`skills`、`source_names`、`timeout_seconds`）的 schema 由后端根据 `node.type` 自动生成，无需 YAML 手写。`parameters` 内部自定义字段由节点 YAML 作者通过 `parameters_schema` 手写。API 返回时两部分合并为完整 schema。

**备选方案**：全自动生成（后端推断所有字段）——否决，因为自定义参数的语义只有 YAML 作者知道。

### D2: 展示层适配器模式

顶层字段在 `NodeConfig` 模型和 YAML 存储中保持不变。API 返回 node type 时，额外生成完整 schema 描述（含顶层字段 + parameters）。Inspector 提交时，后端将 schema 覆盖的字段拆回顶层。运行时继续 `node.model`、`node.skills` 直接访问。

**备选方案**：彻底迁移进 `parameters`——否决，爆炸半径太大，丢失类型安全，运行时全部要改。

### D3: 动态 enum 后端预填充

Schema 中 `source: "skills"` / `source: "models"` 标记由后端在 API 序列化时解析，替换为实际的 `enum: [...]`。前端渲染器只处理标准 JSON Schema，不引入自定义扩展语义。

**备选方案**：前端动态填充（识别 `source` 标记后调用 API）——否决，前端需认自定义扩展，渲染器不再纯粹。

### D4: 第一版字段类型子集

仅支持 `string`、`string + enum`（下拉选择）、`integer/number`（数字输入）、`boolean`（开关）。未匹配的字段类型回退 raw JSON textarea。

### D5: 三级值回退 + 差异保存

显示：instance config 有值 → 类型默认值 → schema default。清空 = 删除实例覆盖。保存时只存与类型默认值不同的字段。UI 用 placeholder 显示类型默认值。

## Risks / Trade-offs

- [后端 schema 合并逻辑复杂度] → 单元测试覆盖合并/拆分路径；schema 合并仅在 API 序列化层，不影响运行时
- [前端渲染器对 JSON Schema 子集的假设] → 严格限定第一版支持的类型；未识别类型回退 textarea
- [skills/models enum 列表变更后缓存] → 每次 API 请求实时生成，不做缓存（列表小，计算成本低）
- [YAML 作者可能写出不合法的 `parameters_schema`] → 后端加载时用 JSON Schema meta-validation 校验
