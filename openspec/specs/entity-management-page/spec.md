# entity-management-page Specification

## Purpose
此规约记录变更 entity-config-page 引入的行为，请在后续同步或归档前补全正式 Purpose。
## Requirements
### Requirement: Entity management page routing

系统 SHALL 在顶级路由 `/entities` 提供实体管理页面，侧边栏新增 Boxes 图标导航入口，位于信息源和节点之间。

#### Scenario: Navigate to entity management

- **WHEN** 用户点击侧边栏实体管理图标
- **THEN** 系统 SHALL 导航到 `/entities` 页面

### Requirement: Tab-based organization

实体管理页面 SHALL 提供三个 tab：类型、实例、关系。

#### Scenario: Switch between tabs

- **WHEN** 用户点击不同 tab
- **THEN** 系统 SHALL 切换显示对应的管理界面

#### Scenario: Default tab

- **WHEN** 用户首次进入 `/entities` 页面
- **THEN** 系统 SHALL 默认展示"类型" tab

### Requirement: Entity type management UI

系统 SHALL 在类型 tab 中以卡片列表展示所有 entity type，每张卡片显示类型名称和 `display_name`，支持 YAML 编辑。

#### Scenario: View entity types

- **WHEN** 用户进入类型 tab
- **THEN** 系统 SHALL 展示所有已定义的 entity type 卡片

#### Scenario: Edit entity type

- **WHEN** 用户点击类型卡片的编辑按钮
- **THEN** 系统 SHALL 打开 YAML 编辑器 dialog，展示该类型的完整 YAML 内容

#### Scenario: Create entity type

- **WHEN** 用户点击"新建类型"按钮
- **THEN** 系统 SHALL 打开 dialog，包含 name 输入框和预填模板的 YAML 编辑器

#### Scenario: Delete entity type with instances

- **WHEN** 用户点击删除按钮且该类型下存在实例
- **THEN** 系统 SHALL 弹出确认 dialog，提示"该类型下有 N 个实例，是否同时删除？"
- **AND** 用户确认后系统 SHALL 调用 cascade 删除 API

#### Scenario: Delete entity type without instances

- **WHEN** 用户点击删除按钮且该类型下无实例
- **THEN** 系统 SHALL 弹出确认 dialog 后直接删除

### Requirement: Entity instance management UI

系统 SHALL 在实例 tab 中按类型分组展示实例卡片，每张卡片显示 `display_template` 渲染结果和关键属性摘要。

#### Scenario: View instances grouped by type

- **WHEN** 用户进入实例 tab
- **THEN** 系统 SHALL 按 entity type 分组展示所有实例卡片

#### Scenario: Create instance

- **WHEN** 用户点击"新建实例"按钮
- **THEN** 系统 SHALL 打开一步式 dialog，顶部为类型选择下拉，下方为 schema-driven 表单

#### Scenario: Type selector changes form

- **WHEN** 用户在新建 dialog 中切换类型选择
- **THEN** 系统 SHALL 根据所选类型的 schema 动态渲染表单字段，清空已填内容

#### Scenario: Edit instance

- **WHEN** 用户点击实例卡片的编辑按钮
- **THEN** 系统 SHALL 打开 schema-driven 表单 dialog，预填当前属性值

#### Scenario: Delete instance with relations

- **WHEN** 用户点击删除按钮且该实例存在关联关系
- **THEN** 系统 SHALL 弹出确认 dialog，提示"将同时移除 N 条关联关系"
- **AND** 用户确认后系统 SHALL 删除实例及相关关系

### Requirement: Schema-driven form rendering

系统 SHALL 根据 entity type 的 `schema` 定义自动生成表单字段。

#### Scenario: String field rendering

- **WHEN** schema 中某字段 `type` 为 `string`
- **THEN** 系统 SHALL 渲染文本输入框

#### Scenario: Object field with properties

- **WHEN** schema 中某字段 `type` 为 `object` 且定义了 `properties`
- **THEN** 系统 SHALL 递归渲染子字段表单

#### Scenario: Object field without properties

- **WHEN** schema 中某字段 `type` 为 `object` 且未定义 `properties`
- **THEN** 系统 SHALL 渲染 JSON 文本输入框作为 fallback

#### Scenario: Read-only field

- **WHEN** entity type 的 `field_permissions` 中某字段为 `read-only`
- **THEN** 系统 SHALL 将该字段渲染为 disabled 输入框（编辑时）

#### Scenario: Required field validation

- **WHEN** schema 的 `required` 数组包含某字段且用户未填写
- **THEN** 系统 SHALL 阻止提交并显示验证错误

### Requirement: Entity relation management UI

系统 SHALL 在关系 tab 中以列表展示所有关系，每行显示两个实体的 display 名称和关系类型。

#### Scenario: View relations

- **WHEN** 用户进入关系 tab
- **THEN** 系统 SHALL 展示所有关系列表

#### Scenario: Create relation

- **WHEN** 用户点击"新建关系"按钮
- **THEN** 系统 SHALL 打开 dialog，包含两个实体选择器和关系类型 combobox

#### Scenario: Relation type combobox suggestions

- **WHEN** 用户聚焦关系类型输入框
- **THEN** 系统 SHALL 从现有关系中提取已用过的类型作为建议列表，同时允许自由输入

#### Scenario: Delete relation

- **WHEN** 用户点击关系行的删除按钮并确认
- **THEN** 系统 SHALL 调用删除 API 移除该条关系

