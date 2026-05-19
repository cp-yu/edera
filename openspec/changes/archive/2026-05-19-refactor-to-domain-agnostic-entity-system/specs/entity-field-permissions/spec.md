## ADDED Requirements

### Requirement: 字段权限枚举值

系统 SHALL 使用枚举值表达字段权限，支持 `read-only`, `write-only`, `none`, `read-write` 四种值。

#### Scenario: read-only 权限

- **WHEN** 字段权限设置为 `read-only`
- **THEN** 节点可以读取该字段，但不能修改

#### Scenario: write-only 权限

- **WHEN** 字段权限设置为 `write-only`
- **THEN** 节点可以修改该字段，但不能读取

#### Scenario: none 权限

- **WHEN** 字段权限设置为 `none`
- **THEN** 节点不能读取也不能修改该字段

#### Scenario: read-write 权限（默认）

- **WHEN** 字段权限未声明或设置为 `read-write`
- **THEN** 节点可以读取和修改该字段

### Requirement: 权限继承

系统 SHALL 支持嵌套字段继承父字段的权限。

#### Scenario: 父字段权限继承

- **WHEN** `holding` 字段权限设置为 `read-only`，未单独声明 `holding.quantity` 权限
- **THEN** `holding.quantity` 继承 `read-only` 权限

#### Scenario: 子字段覆盖父字段权限

- **WHEN** `holding` 字段权限设置为 `read-only`，但 `holding.quantity` 单独声明为 `read-write`
- **THEN** `holding.quantity` 使用 `read-write` 权限，其他子字段继承 `read-only`

### Requirement: 配置时权限验证

系统 SHALL 在保存 DAG 配置时验证节点的 `entity_permissions` 是否合法，只能提权不能降权。

#### Scenario: 合法提权

- **WHEN** 节点配置 `entity_permissions: {stock: {code: read-write}}`，默认权限是 `read-only`
- **THEN** 系统接受配置，保存成功

#### Scenario: 非法降权

- **WHEN** 节点配置 `entity_permissions: {stock: {holding: read-only}}`，默认权限是 `read-write`
- **THEN** 系统拒绝配置，返回错误 "Cannot downgrade permission for stock.holding from read-write to read-only"

#### Scenario: 提权到相同级别

- **WHEN** 节点配置 `entity_permissions: {stock: {code: read-only}}`，默认权限也是 `read-only`
- **THEN** 系统接受配置（虽然冗余，但不报错）

### Requirement: 运行时权限检查

系统 SHALL 在节点执行时检查每次字段访问是否符合权限，违反时发出警告并阻止操作。

#### Scenario: 读取权限检查

- **WHEN** 节点尝试读取权限为 `write-only` 或 `none` 的字段
- **THEN** 系统记录警告日志 "Permission denied: <entity_type>.<field> is not readable"，返回 None

#### Scenario: 写入权限检查

- **WHEN** 节点尝试修改权限为 `read-only` 或 `none` 的字段
- **THEN** 系统记录警告日志 "Permission denied: <entity_type>.<field> is not writable"，不保存修改

#### Scenario: 批量保存时过滤受保护字段

- **WHEN** 节点修改多个字段后调用 `context.save_entity(entity)`，其中部分字段受保护
- **THEN** 系统只保存允许修改的字段，受保护字段保持原值，记录警告日志

### Requirement: 权限提升路径

系统 SHALL 定义权限提升的合法路径，`none` 可以提升到任意权限，`read-only` 和 `write-only` 可以提升到 `read-write`。

#### Scenario: none 提升到 read-only

- **WHEN** 默认权限是 `none`，节点配置 `entity_permissions: {stock: {internal_notes: read-only}}`
- **THEN** 系统接受配置（合法提权）

#### Scenario: none 提升到 read-write

- **WHEN** 默认权限是 `none`，节点配置 `entity_permissions: {stock: {internal_notes: read-write}}`
- **THEN** 系统接受配置（合法提权）

#### Scenario: read-only 提升到 read-write

- **WHEN** 默认权限是 `read-only`，节点配置 `entity_permissions: {stock: {code: read-write}}`
- **THEN** 系统接受配置（合法提权）

#### Scenario: write-only 提升到 read-write

- **WHEN** 默认权限是 `write-only`，节点配置 `entity_permissions: {stock: {api_key: read-write}}`
- **THEN** 系统接受配置（合法提权）

#### Scenario: read-only 降级到 none

- **WHEN** 默认权限是 `read-only`，节点配置 `entity_permissions: {stock: {code: none}}`
- **THEN** 系统拒绝配置（非法降权）
