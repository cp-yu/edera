## Why

Portfolio 配置已废弃（API 返回 404），但前端仍展示死代码 tab。同时，entity 系统虽然后端完整（类型定义、实例存储、关系），但缺少独立的管理 UI — 用户无法通过 Web 界面进行实体类型/实例/关系的 CRUD 操作。此外，pipeline services 仍通过 `PortfolioConfig` 兼容层间接访问实体数据，增加了不必要的抽象层。

## What Changes

- 删除 ConfigPage 的 Portfolio tab，简化为仅展示 System 配置编辑器（去掉 tab 切换）
- 新增独立顶级页面 `/entities`（侧边栏 Boxes 图标，位于信息源和节点之间）
- 页面包含三个 tab：类型 / 实例 / 关系
  - 类型 tab：全 YAML 编辑器，支持完整 CRUD（新建时 name 输入 + YAML 模板）
  - 实例 tab：卡片列表 + schema-driven 表单 dialog（一步式，顶部类型选择器）
  - 关系 tab：列表展示 + 单条 CRUD（关系加 UUID ID，关系类型 combobox）
- 新增后端 API：entity type CRUD、单实例 CRUD（复用 EntityStore）、单条关系 CRUD
- 删除类型时后端拒绝（有实例），前端提供 cascade 选项同时删除实例
- 删除实例时自动级联删除相关关系，前端提示
- **BREAKING**: 重构 pipeline services 直接使用 `EntityStore`，删除 `PortfolioConfig`、`TargetConfig`、`SourceConfig`、`Holding` 类及 `config/portfolio.yaml`
- 删除后端 portfolio 相关 route 和 editor 分支

## Capabilities

### New Capabilities
- `entity-management-page`: 实体管理独立页面，覆盖类型/实例/关系三个 tab 的 CRUD 交互、schema-driven 表单、级联删除确认
- `entity-type-crud-api`: Entity Type 后端 CRUD API，覆盖创建/读取/更新/删除类型定义文件，含 cascade 删除参数
- `entity-instance-crud-api`: Entity Instance 单条 CRUD API，复用 EntityStore 逻辑
- `entity-relation-crud-api`: Entity Relation 单条 CRUD API，关系加 UUID 标识

### Modified Capabilities
- `entity-system`: pipeline services 从 PortfolioConfig 兼容层迁移到直接使用 EntityStore
- `runtime-config-editing`: 移除 portfolio 配置编辑相关行为，ConfigPage 简化为仅 System 编辑器

## Impact

- **后端**: `src/stockimformation/web/routes.py` 新增 entity type/instance/relation CRUD endpoints；`src/stockimformation/config/schema.py` 删除 PortfolioConfig/TargetConfig/SourceConfig/Holding；`src/stockimformation/services/` 重构为使用 EntityStore；`src/stockimformation/pipeline.py` 重构 handler 构造；`src/stockimformation/config/editor.py` 清理 portfolio 分支
- **前端**: 新增 `frontend/src/features/entities/` 目录；修改 `ConfigPage.tsx` 简化；修改 `SideNav.tsx` 和 `router/index.tsx` 增加路由
- **配置文件**: 删除 `config/portfolio.yaml`；`config/entity-relations.yaml` 结构变更（每条关系增加 `id` 字段）
- **依赖**: 无新外部依赖
