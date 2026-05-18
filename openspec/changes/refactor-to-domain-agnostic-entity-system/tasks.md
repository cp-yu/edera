## 1. Actions

- [ ] A1 创建 entity types schema 定义（stock, city, rss-source, web-source）
- [ ] A2 创建 entities.yaml 配置文件结构和加载逻辑
- [ ] A3 创建 entity-relations.yaml 配置文件结构和加载逻辑
- [ ] A4 实现实体引用解析（UUID 和业务 ID 双模式）
- [ ] A5 实现字段权限系统（黑名单机制、枚举值、继承）
- [ ] A6 实现节点实例权限提权验证（配置时检查）
- [ ] A7 实现节点执行时权限检查（运行时检查）
- [ ] A8 实现节点上下文实体访问接口（get_entity, save_entity, create_entity）
- [ ] A9 实现实体自动发现逻辑（从 entity-relations.yaml）
- [ ] A10 修改 RawItem 模型（stock_codes → tags）
- [ ] A11 创建数据库迁移脚本（stock_codes → tags）
- [ ] A12 新增实体配置 API 端点（GET/POST /api/config/entities）
- [ ] A13 新增关系配置 API 端点（GET/POST /api/config/entity-relations）
- [ ] A14 废弃 portfolio 配置 API 端点
- [ ] A15 修改节点实例模型（新增 entities 和 entity_permissions 字段）
- [ ] A16 修改 DAG YAML 序列化（包含 entities 和 entity_permissions）
- [ ] A17 实现 Inspector 实体选择器组件
- [ ] A18 实现 Inspector 权限配置器组件
- [ ] A19 修改底部工具栏（target 过滤器 → entity 过滤器）
- [ ] A20 创建 portfolio.yaml 到 entities.yaml 的迁移脚本

## 2. Checks

- [ ] C1 验证 entity types schema 加载
  - Covers: A1
  - Command: `pytest tests/unit/test_entity_types.py -k test_load_stock_schema`
  - Expect: 加载 stock.yaml，验证 business_id_field, display_template, field_permissions 字段

- [ ] C2 验证 entities.yaml 加载和验证
  - Covers: A2
  - Command: `pytest tests/unit/test_entities_config.py -k test_load_entities`
  - Expect: 加载 entities.yaml，验证实体类型存在，attributes 符合 schema

- [ ] C3 验证 entity-relations.yaml 加载
  - Covers: A3
  - Command: `pytest tests/unit/test_entity_relations.py -k test_load_relations`
  - Expect: 加载 entity-relations.yaml，验证关系格式正确

- [ ] C4 验证 UUID 引用解析
  - Covers: A4
  - Command: `pytest tests/unit/test_entity_reference.py -k test_resolve_uuid`
  - Expect: 输入 UUID，返回对应实体

- [ ] C5 验证业务 ID 引用解析
  - Covers: A4
  - Command: `pytest tests/unit/test_entity_reference.py -k test_resolve_business_id`
  - Expect: 输入 "stock:00700.HK"，根据 business_id_field 查找实体

- [ ] C6 验证字段权限黑名单机制
  - Covers: A5
  - Command: `pytest tests/unit/test_field_permissions.py -k test_default_read_write`
  - Expect: 未声明权限的字段默认为 read-write

- [ ] C7 验证权限枚举值
  - Covers: A5
  - Command: `pytest tests/unit/test_field_permissions.py -k test_permission_enum`
  - Expect: 支持 read-only, write-only, none, read-write 四种值

- [ ] C8 验证权限继承
  - Covers: A5
  - Command: `pytest tests/unit/test_field_permissions.py -k test_permission_inheritance`
  - Expect: 子字段继承父字段权限

- [ ] C9 验证提权合法性检查
  - Covers: A6
  - Command: `pytest tests/unit/test_permission_escalation.py -k test_valid_escalation`
  - Expect: none → read-only, read-only → read-write 允许

- [ ] C10 验证降权拒绝
  - Covers: A6
  - Command: `pytest tests/unit/test_permission_escalation.py -k test_invalid_downgrade`
  - Expect: read-write → read-only 拒绝，返回错误

- [ ] C11 验证运行时读权限检查
  - Covers: A7
  - Command: `pytest tests/unit/test_runtime_permissions.py -k test_read_protected_field`
  - Expect: 读取 none 或 write-only 字段，记录警告，返回 None

- [ ] C12 验证运行时写权限检查
  - Covers: A7
  - Command: `pytest tests/unit/test_runtime_permissions.py -k test_write_protected_field`
  - Expect: 修改 none 或 read-only 字段，记录警告，不保存

- [ ] C13 验证 get_entity 接口
  - Covers: A8
  - Command: `pytest tests/unit/test_node_context.py -k test_get_entity`
  - Expect: 调用 context.get_entity("stock:00700.HK")，返回实体对象

- [ ] C14 验证 save_entity 接口
  - Covers: A8
  - Command: `pytest tests/unit/test_node_context.py -k test_save_entity`
  - Expect: 修改实体后保存，检查权限，只保存允许的字段

- [ ] C15 验证 create_entity 接口
  - Covers: A8
  - Command: `pytest tests/unit/test_node_context.py -k test_create_entity`
  - Expect: 创建新实体，生成 UUID，验证 attributes，保存到配置

- [ ] C16 验证实体自动发现
  - Covers: A9
  - Command: `pytest tests/unit/test_entity_auto_discovery.py -k test_discover_from_source`
  - Expect: 节点配置 source 未配置 entities，从 entity-relations.yaml 发现关联实体

- [ ] C17 验证显式配置优先
  - Covers: A9
  - Command: `pytest tests/unit/test_entity_auto_discovery.py -k test_explicit_override`
  - Expect: 节点配置 entities，忽略自动发现

- [ ] C18 验证 RawItem.tags 字段
  - Covers: A10
  - Command: `pytest tests/unit/test_raw_item_model.py -k test_tags_field`
  - Expect: RawItem 模型有 tags 字段，类型为 list[str]

- [ ] C19 验证数据库迁移脚本
  - Covers: A11
  - Command: `pytest tests/integration/test_migration.py -k test_stock_codes_to_tags`
  - Expect: 运行迁移，stock_codes 列改为 tags，数据转换正确

- [ ] C20 验证 GET /api/config/entities
  - Covers: A12
  - Command: `pytest tests/integration/test_config_api.py -k test_get_entities`
  - Expect: 返回 entities.yaml 内容

- [ ] C21 验证 POST /api/config/entities
  - Covers: A12
  - Command: `pytest tests/integration/test_config_api.py -k test_save_entities`
  - Expect: 保存合法配置，验证实体类型和 schema

- [ ] C22 验证 GET /api/config/entity-relations
  - Covers: A13
  - Command: `pytest tests/integration/test_config_api.py -k test_get_relations`
  - Expect: 返回 entity-relations.yaml 内容

- [ ] C23 验证 POST /api/config/entity-relations
  - Covers: A13
  - Command: `pytest tests/integration/test_config_api.py -k test_save_relations`
  - Expect: 保存合法配置，验证引用的实体存在

- [ ] C24 验证 portfolio API 端点废弃
  - Covers: A14
  - Command: `pytest tests/integration/test_config_api.py -k test_portfolio_deprecated`
  - Expect: GET /api/config/portfolio 返回 404 或废弃提示

- [ ] C25 验证节点实例模型新增字段
  - Covers: A15
  - Command: `pytest tests/unit/test_node_instance_model.py -k test_entities_field`
  - Expect: DagNodeInstance 模型有 entities 和 entity_permissions 字段

- [ ] C26 验证 DAG YAML 序列化
  - Covers: A16
  - Command: `pytest tests/unit/test_dag_serialization.py -k test_serialize_with_entities`
  - Expect: 保存 DAG，config 包含 entities 和 entity_permissions

- [ ] C27 验证 Inspector 实体选择器渲染
  - Covers: A17
  - Evidence: 手动测试 Inspector UI
  - Expect: 显示实体选择器，按类型分组，优先显示关联实体

- [ ] C28 验证 Inspector 实体选择器保存
  - Covers: A17
  - Command: `pytest tests/e2e/test_inspector.py -k test_save_entities`
  - Expect: 选择实体后保存，entities 字段写入节点 config

- [ ] C29 验证 Inspector 权限配置器渲染
  - Covers: A18
  - Evidence: 手动测试 Inspector UI
  - Expect: 显示权限覆盖区域，可添加字段权限覆盖

- [ ] C30 验证 Inspector 权限配置器保存
  - Covers: A18
  - Command: `pytest tests/e2e/test_inspector.py -k test_save_permissions`
  - Expect: 配置权限后保存，entity_permissions 字段写入节点 config

- [ ] C31 验证 entity 过滤器渲染
  - Covers: A19
  - Evidence: 手动测试底部工具栏
  - Expect: 显示 entity 过滤器，包含所有类型的实体

- [ ] C32 验证 entity 过滤器功能
  - Covers: A19
  - Evidence: 手动测试过滤效果
  - Expect: 选择 entity 后，不匹配节点透明度降低

- [ ] C33 验证迁移脚本执行
  - Covers: A20
  - Command: `python scripts/migrate_portfolio.py`
  - Expect: 生成 entities.yaml 和 entity-relations.yaml，内容正确

- [ ] C34 验证迁移脚本数据完整性
  - Covers: A20
  - Evidence: 对比迁移前后配置
  - Expect: 所有 targets 和 sources 转换为 entities，关系正确
