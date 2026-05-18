## Why

当前节点系统将类型定义和 DAG 实例混为一体——同一个 type name 既是定义标识又是实例标识，导致同类型节点无法多实例化、信息流无约束（source 节点可以接收输入、sink 节点可以输出）、LLM 和 Function 节点共用 `skills` 字段但语义完全不同。需要建立 NodeType / NodeInstance 分层模型，使 DAG 编辑具备真正的图编辑能力。

## What Changes

- **BREAKING** DAG YAML 格式从 type-name 列表改为 instance 对象列表（UUID id + type 引用 + 实例配置）
- **BREAKING** 节点类型 YAML 新增 `role: source | processor | sink` 显式声明
- **BREAKING** Function 节点的 `skills` 字段重命名为 `handler`，与 LLM 节点的 skills 概念分离
- LLM 节点类型新增 `system_prompt_file` 字段，引用外部 prompt 文件
- 新增独立 Skill 注册目录 `config/skills/`，每个 skill 有独立定义文件
- 新增 Function handler 约定目录 `handlers/`，支持 `importlib` 动态加载
- 前端支持同类型多实例拖入 DAG，实例使用 UUID 标识 + 可选别名
- 连线校验分层：Function 节点类型不匹配硬阻止，LLM 节点类型不匹配软警告
- Handle 渲染按 role 驱动：source 无输入 handle，sink 无输出 handle
- 新增节点管理页面 `/nodes`（LLM 节点 / Function 节点 / Skills 三个 tab）
- Inspector 支持选中边后配置 `fan_in` / `fan_out`
- QuickAddPanel 按 role 分组展示，支持实例别名搜索

## Capabilities

### New Capabilities
- `node-type-registry`: 节点类型注册与管理，覆盖 LLM/Function 类型定义、YAML 格式、role 声明、handler/prompt 绑定
- `skill-registry`: Skill 独立注册与管理，覆盖 skill 定义文件结构、参数 schema、handler 绑定
- `node-instance-model`: 节点实例化模型，覆盖 UUID 标识、别名、实例级配置（skills/model/parameters/source_names）、多实例支持
- `connection-type-validation`: 连线类型校验，覆盖 role 约束（source 无入边/sink 无出边）、I/O 类型匹配规则、实时拖拽反馈
- `node-management-page`: 节点管理页面，覆盖 LLM 类型创建编辑、Function 类型创建与代码编辑、Skill CRUD

### Modified Capabilities
- `dag-workbench-ui`: QuickAddPanel 按 role 分组、去掉去重限制、Inspector 支持边配置
- `node-graph-dag-editor`: DAG YAML 格式变更为 instance 模型、handle 按 role 渲染
- `node-visual-system`: Handle 可见性由 role 驱动、连线校验视觉反馈
- `node-executor`: 后端按 instance ID 调度、handler 动态加载机制

## Impact

- `config/nodes/*.yaml`: 格式重构（新增 role、handler 替代 skills、system_prompt_file）
- `config/dags/default.yaml`: 一次性手动迁移为新格式
- `config/skills/`: 新目录，skill 定义文件
- `handlers/`: 新目录，function handler Python 文件
- `prompts/`: 新目录，LLM system prompt 文件
- `src/stockimformation/web/routes.py`: 新增节点类型/skill CRUD API
- `src/stockimformation/`: 节点加载、DAG 解析、运行状态索引改为 instance ID
- `frontend/src/api/types.ts`: TypeScript 类型重构（NodeType vs NodeInstance）
- `frontend/src/features/workbench/`: Canvas、Inspector、QuickAddPanel、graph.ts 全面适配
- `frontend/src/features/nodes/`: 新增节点管理页面
- `frontend/src/router/index.tsx`: 新增 `/nodes` 路由
- `frontend/src/components/layout/SideNav.tsx`: 新增导航入口
