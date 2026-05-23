## ADDED Requirements

### Requirement: Manifest 表声明

扩展 manifest MAY 包含 `storage.tables` 段，声明扩展所需的自定义数据库表。每个表声明 MUST 包含 `name` 和 `columns` 字段。

#### Scenario: 声明自定义表

- **WHEN** manifest 包含 `storage.tables` 段，声明表 `raw_items` 含 `id`、`url`、`title` 列
- **THEN** 核心 SHALL 在 bootstrap 时根据声明自动创建该表

#### Scenario: 表已存在

- **WHEN** 核心 bootstrap 发现声明的表已存在于数据库中
- **THEN** 核心 SHALL 跳过建表，不报错

#### Scenario: 表声明缺少必填字段

- **WHEN** manifest `storage.tables` 条目缺少 `name` 或 `columns`
- **THEN** 核心 SHALL 拒绝该表声明并记录校验错误

### Requirement: 列类型支持

核心 SHALL 支持以下列类型声明：`integer`、`text`、`real`、`datetime`、`boolean`、`json`。列声明 MAY 包含 `primary_key`、`unique`、`index`、`nullable` 属性。

#### Scenario: 创建带索引的表

- **WHEN** 表声明包含 `{name: source_name, type: text, index: true}`
- **THEN** 核心 SHALL 创建该列并为其建立索引

#### Scenario: 主键列

- **WHEN** 表声明包含 `{name: id, type: integer, primary_key: true}`
- **THEN** 核心 SHALL 将该列设为主键（自增）

#### Scenario: 不支持的列类型

- **WHEN** 表声明包含未知类型（如 `{type: blob}`）
- **THEN** 核心 SHALL 拒绝该表声明并记录错误

### Requirement: 扩展表命名空间隔离

核心 SHALL 为扩展创建的表添加命名前缀 `ext_`，避免与核心表冲突。

#### Scenario: 表名自动加前缀

- **WHEN** 扩展 `rss-fetcher` 声明表 `raw_items`
- **THEN** 核心 SHALL 创建实际表名为 `ext_rss_fetcher_raw_items`

#### Scenario: 扩展访问自己的表

- **WHEN** handler 需要访问自己声明的表
- **THEN** 核心 SHALL 通过 `HandlerContext` 提供表访问接口，handler 使用声明时的逻辑表名（`raw_items`），核心自动映射到实际表名
