## 1. Actions

- [x] A1 后端：新增 Entity Type CRUD API endpoints（`GET/POST /api/config/entity-types`、`GET/PUT/DELETE /api/config/entity-types/{name}`），含 cascade 删除参数
- [x] A2 后端：新增 Entity Instance 单条 CRUD endpoints（`GET /api/entities`、`POST /api/entities`、`PUT /api/entities/{id}`、`DELETE /api/entities/{id}`），复用 EntityStore
- [x] A3 后端：`EntityRelationConfig` 增加 `id` 字段，加载时自动补全缺失 ID；新增单条关系 CRUD endpoints（`GET /api/entity-relations`、`GET /api/entity-relations/types`、`POST /api/entity-relations`、`DELETE /api/entity-relations/{id}`）
- [x] A4 后端：重构 pipeline services（collection、advisory、briefing）直接使用 EntityStore，移除对 PortfolioConfig 的依赖
- [x] A5 后端：删除 PortfolioConfig、TargetConfig、SourceConfig、Holding 类，删除 `EntitiesConfig.to_portfolio()` 方法，删除 `load_portfolio_config()` 函数，清理 editor.py 中 portfolio 分支
- [x] A6 后端：删除 portfolio 相关 route（`api_portfolio_save`、`api_config_portfolio_read`），从 ConfigKind 中移除 `"portfolio"`
- [x] A7 删除 `config/portfolio.yaml` 文件
- [x] A8 前端：新增 `frontend/src/features/entities/EntitiesPage.tsx`，包含类型/实例/关系三个 tab
- [x] A9 前端：实现类型 tab — 卡片列表 + YAML 编辑 dialog（新建时 name 输入 + YAML 模板）+ cascade 删除确认
- [x] A10 前端：实现实例 tab — 按类型分组卡片列表 + schema-driven 表单 dialog（一步式，顶部类型选择器，混合策略渲染）
- [x] A11 前端：实现关系 tab — 关系列表 + 新建 dialog（两个实体选择器 + 关系类型 combobox）+ 删除确认
- [x] A12 前端：修改 `SideNav.tsx` 增加 Boxes 图标入口（位于信息源和节点之间），修改 `router/index.tsx` 增加 `/entities` 路由
- [x] A13 前端：简化 `ConfigPage.tsx` — 删除 Portfolio tab 和相关 state/query/mutation，去掉 tab 切换，直接展示 System 编辑器

## 2. Checks

- [x] C1 验证 Entity Type CRUD API 正常工作
  - Covers: A1
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/ -k "entity_type" -v`
  - Expect: 所有 entity type CRUD 测试通过（list、read、create、update、delete、cascade delete）

- [x] C2 验证 Entity Instance 单条 CRUD API 正常工作
  - Covers: A2
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/ -k "entity_instance" -v`
  - Expect: 所有 entity instance CRUD 测试通过（list、filter、create、update、delete with cascade relations）

- [x] C3 验证 Entity Relation CRUD API 正常工作（含 UUID ID 自动补全）
  - Covers: A3
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/ -k "entity_relation" -v`
  - Expect: 所有 entity relation CRUD 测试通过（list、list types、create、delete、auto-assign ID）

- [x] C4 验证 pipeline services 重构后行为等价
  - Covers: A4
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/ -k "collection or advisory or briefing" -v`
  - Expect: 所有 pipeline service 测试通过，services 使用 EntityStore 获取等价数据

- [x] C5 验证 PortfolioConfig 及相关代码完全移除
  - Covers: A5, A6, A7
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && grep -r "PortfolioConfig\|TargetConfig\|SourceConfig\|class Holding" src/ && echo "FAIL: references remain" || echo "PASS: clean removal"`
  - Expect: 输出 "PASS: clean removal"，无残留引用

- [x] C6 验证 portfolio.yaml 已删除且 portfolio route 返回 404 或不存在
  - Covers: A6, A7
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && test ! -f config/portfolio.yaml && grep -c "api_portfolio_save\|api_config_portfolio_read" src/stockimformation/web/routes.py | grep "^0$" && echo "PASS" || echo "FAIL"`
  - Expect: 输出 "PASS"

- [x] C7 验证前端 EntitiesPage 路由和导航正常
  - Covers: A8, A12
  - Evidence: 浏览器访问 `http://localhost:5173/entities`
  - Expect: 页面正常渲染，侧边栏 Boxes 图标高亮，三个 tab 可切换

- [x] C8 验证类型 tab CRUD 交互
  - Covers: A9
  - Evidence: 浏览器操作类型 tab
  - Expect: 可查看所有类型卡片；新建类型（name + YAML）成功；编辑类型 YAML 保存成功；删除有实例的类型弹出 cascade 确认

- [x] C9 验证实例 tab schema-driven 表单
  - Covers: A10
  - Evidence: 浏览器操作实例 tab
  - Expect: 按类型分组展示卡片；新建实例 dialog 切换类型时表单动态变化；read-only 字段 disabled；嵌套 object 无 properties 时显示 JSON 文本框

- [x] C10 验证关系 tab CRUD 交互
  - Covers: A11
  - Evidence: 浏览器操作关系 tab
  - Expect: 关系列表正常展示；新建关系 combobox 显示已有类型建议；删除关系成功

- [x] C11 验证 ConfigPage 简化后正常工作
  - Covers: A13
  - Evidence: 浏览器访问 `http://localhost:5173/config`
  - Expect: 无 tab 切换，直接展示 System TOML 编辑器；无 Portfolio 相关 UI

- [x] C12 验证全量测试通过
  - Covers: A1, A2, A3, A4, A5, A6, A7
  - Command: `cd /home/yunxin/Documents/Code/tools/stockImformation && python -m pytest tests/ -v`
  - Expect: 所有测试通过，无回归

## Remediation

- [x] [code_fix] ConfigPage save endpoint is not routable: wire System config save to a backend PUT route that validates and persists System config.
