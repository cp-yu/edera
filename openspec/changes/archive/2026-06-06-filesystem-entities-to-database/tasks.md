# Implementation Tasks

### Task 1: 创建 EntityRelation 数据库表

**Goal**: 创建 `entity_relations` 表，存储所有 entity relations。

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Create: `packages/core/src/edera_core/storage/migrations/0011_entity_relations.py`
- Test: `packages/core/tests/test_entity_relations_storage.py`

**Requirements**:
- 定义 `EntityRelation` SQLModel 类
- 包含字段：id, from_entity_id, to_entity_id, relation_type, metadata, created_at, updated_at
- 添加唯一约束和索引
- 创建数据库迁移脚本

#### Checks

- [x] C1 验证表结构创建
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "Entity relations 存储到数据库" / Scenario "创建 relation"
  - Command: `pytest packages/core/tests/test_entity_relations_storage.py::test_create_table -v`
  - Expect: 表创建成功，包含所有字段和索引

- [x] C2 验证唯一约束
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "Entity relations 存储到数据库" / Scenario "Relation 唯一性约束"
  - Command: `pytest packages/core/tests/test_entity_relations_storage.py::test_unique_constraint -v`
  - Expect: 相同 (from, to, type) 的 relation 不能重复创建

### Task 2: 实现 entity 和 relation CRUD

**Goal**: 实现 entity 和 relation 的数据库 CRUD 操作。

**Files**:
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `packages/core/tests/test_entity_repository.py`
- Test: `packages/core/tests/test_relation_repository.py`

**Requirements**:
- 实现 `create_ordinary_entity()`, `update_ordinary_entity()`, `delete_ordinary_entity()`
- 实现 `list_ordinary_entities()` 按 type 查询
- 实现 `create_relation()`, `delete_relation()`, `list_relations()`
- Relations 查询支持按 from, to, type 过滤

#### Checks

- [x] C3 验证创建 ordinary entity
  - Verifies: `specs/ordinary-entity-database-storage/spec.md` / Requirement "Entity CRUD 操作" / Scenario "创建 entity"
  - Command: `pytest packages/core/tests/test_entity_repository.py::test_create_ordinary_entity -v`
  - Expect: Entity 创建成功并保存到对应表

- [x] C4 验证更新 entity
  - Verifies: `specs/ordinary-entity-database-storage/spec.md` / Requirement "Entity CRUD 操作" / Scenario "更新 entity"
  - Command: `pytest packages/core/tests/test_entity_repository.py::test_update_entity -v`
  - Expect: Attributes 合并并更新到数据库

- [x] C5 验证删除 entity 检查 relations
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "删除 entity 时检查 relations" / Scenario "Entity 被 relations 引用时拒绝删除"
  - Command: `pytest packages/core/tests/test_entity_repository.py::test_delete_entity_with_relations -v`
  - Expect: 拒绝删除并返回 relations 列表

- [x] C6 验证创建 relation
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "Entity relations 存储到数据库" / Scenario "创建 relation"
  - Command: `pytest packages/core/tests/test_relation_repository.py::test_create_relation -v`
  - Expect: Relation 创建成功

- [x] C7 验证查询 relations
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "查询 entity relations" / Scenario "组合查询"
  - Command: `pytest packages/core/tests/test_relation_repository.py::test_list_relations_filter -v`
  - Expect: 按 from/to/type 过滤查询正确

### Task 3: 实现 YAML 导入导出

**Goal**: 实现 entities 和 relations 的 YAML 导入导出功能。

**Files**:
- Create: `packages/core/src/edera_core/storage/import_export.py`
- Test: `packages/core/tests/test_import_export.py`

**Requirements**:
- 实现 `import_entities_from_yaml()` 批量导入
- 实现 `export_entities_to_yaml()` 导出
- 实现 `import_relations_from_yaml()` 批量导入
- 实现 `export_relations_to_yaml()` 导出
- YAML 格式与现有文件兼容

#### Checks

- [x] C8 验证导入 entities
  - Verifies: `specs/ordinary-entity-database-storage/spec.md` / Requirement "从文件导入 entities" / Scenario "导入 YAML 文件"
  - Command: `pytest packages/core/tests/test_import_export.py::test_import_entities -v`
  - Expect: YAML 文件中的 entities 批量导入成功

- [x] C9 验证导入时 ID 冲突处理
  - Verifies: `specs/ordinary-entity-database-storage/spec.md` / Requirement "从文件导入 entities" / Scenario "导入时 ID 冲突"
  - Command: `pytest packages/core/tests/test_import_export.py::test_import_conflict -v`
  - Expect: 更新现有 entity

- [x] C10 验证导出 entities
  - Verifies: `specs/ordinary-entity-database-storage/spec.md` / Requirement "导出 entities 到文件" / Scenario "导出所有 entities"
  - Command: `pytest packages/core/tests/test_import_export.py::test_export_entities -v`
  - Expect: 生成 YAML 文件包含所有 entities

- [x] C11 验证导入 relations
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "Relations 批量导入导出" / Scenario "从 YAML 导入 relations"
  - Command: `pytest packages/core/tests/test_import_export.py::test_import_relations -v`
  - Expect: Relations 批量导入成功

- [x] C12 验证导入时跳过无效 relations
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "Relations 批量导入导出" / Scenario "导入时引用的 entity 不存在"
  - Command: `pytest packages/core/tests/test_import_export.py::test_import_invalid_relations -v`
  - Expect: 跳过无效 relation，记录警告

### Task 4: 修改 EntityStore 支持按需预加载

### Task 4: 修改 EntityStore 支持按需预加载

**Goal**: 修改 `EntityStore` 支持按需预加载、DAG 生命周期缓存和查询结果包装。

**Files**:
- Modify: `packages/core/src/edera_core/config/entities.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Create: `packages/core/src/edera_core/config/entity_query_result.py`
- Test: `packages/core/tests/test_entity_store_preload.py`

**Requirements**:
- 新增 `EntityQueryResult` 包装类（entity, from_cache, dag_run_id）
- 修改 `memory_entities` 为按 dag_run_id 分组的缓存结构
- 新增 `preload_for_dag(dag_run_id, entity_refs)` 方法：批量加载 entities 到缓存
- 修改查询接口：支持传递 `dag_run_id`，优先查缓存，未命中查数据库，返回 `EntityQueryResult`
- 新增 `clear_cache_for_dag(dag_run_id)` 方法：清理指定 DAG 的缓存
- 移除从 `config/entities.yaml` 和 `config/entity-relations.yaml` 加载逻辑
- 预加载失败（entity 不存在）时抛出异常

#### Checks

- [x] C13 验证 EntityQueryResult 包装
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "统一 Entity 原语" / Scenario "普通业务 Entity 从数据库加载"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_query_result_wrapper -v`
  - Expect: 查询返回 EntityQueryResult，包含 entity、from_cache、dag_run_id 字段

- [x] C14 验证 DAG 预加载
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "统一 Entity 原语" / Scenario "DAG 作为 Entity"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_preload_for_dag -v`
  - Expect: preload_for_dag 批量加载 entities 到 memory_entities[dag_run_id]

- [x] C15 验证缓存命中查询
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "Entity 统一 CRUD 接口" / Scenario "通过统一接口创建普通 Entity"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_query_from_cache -v`
  - Expect: 带 dag_run_id 查询时优先返回缓存，from_cache=True

- [x] C16 验证缓存未命中查询数据库
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "Entity 统一 CRUD 接口" / Scenario "通过统一接口创建普通 Entity"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_query_fallback_to_db -v`
  - Expect: 缓存未命中时查数据库，from_cache=False，不缓存结果

- [x] C17 验证非 DAG 上下文查询
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心配置型 Entity 使用 DB source of truth" / Scenario "运行时从 DB 读取普通 Entity"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_query_without_dag_context -v`
  - Expect: 无 dag_run_id 时直接查数据库，from_cache=False

- [x] C18 验证缓存清理
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "统一 Entity 原语" / Scenario "DAG 作为 Entity"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_clear_cache -v`
  - Expect: clear_cache_for_dag 删除指定 dag_run_id 的缓存

- [x] C19 验证预加载失败抛出异常
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "Entity 统一 CRUD 接口" / Scenario "通过统一接口创建普通 Entity"
  - Command: `pytest packages/core/tests/test_entity_store_preload.py::test_preload_entity_not_found -v`
  - Expect: 预加载不存在的 entity 时抛出异常

- [x] C20 验证不再读取 YAML 文件
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心配置型 Entity 使用 DB source of truth" / Scenario "运行时从 DB 读取普通 Entity"
  - Evidence: `packages/core/src/edera_core/config/loader.py`
  - Expect: 移除 `load_entities_config()` 和 `load_entity_relations_config()` 调用

### Task 5: 实现 edera entity CLI 命令

### Task 5: 实现 edera entity CLI 命令（含 relation 别名）

**Goal**: 实现 `edera entity` 子命令组，支持通用列过滤，并提供 `edera relation` 别名。

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Create: `packages/core/src/edera_core/cli/entity_commands.py`
- Create: `packages/core/src/edera_core/cli/relation_aliases.py`
- Test: `packages/core/tests/test_cli_entity.py`
- Test: `packages/core/tests/test_cli_relation_aliases.py`

**Requirements**:
- 实现 `entity list`, `show`, `create`, `update`, `delete` 命令
- 实现 `entity import`, `export` 命令
- 支持 `--type`, `--filter` 等参数，`--filter` 支持多次使用（AND 逻辑）
- 实现 `relation list`, `create`, `delete`, `import`, `export` 别名
- Relation 别名内部转换为 entity 命令调用

#### Checks

- [x] C21 验证 entity list 通用过滤
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Entity list 命令" / Scenario "通用列过滤"
  - Command: `edera entity list --type relation --filter from_entity_id=stock:test`
  - Expect: 返回满足条件的 relations

- [x] C22 验证 entity list 多列组合过滤
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Entity list 命令" / Scenario "多列组合过滤"
  - Command: `edera entity list --type relation --filter from_entity_id=stock:test --filter relation_type=uses-source`
  - Expect: 应用 AND 逻辑，返回满足所有条件的结果

- [x] C23 验证 entity create 命令
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Entity create 命令" / Scenario "创建 entity"
  - Command: `edera entity create --type stock --id test-stock --attributes '{"code":"TEST","name":"Test"}'`
  - Expect: Entity 创建成功

- [x] C24 验证 entity import 命令
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Entity import 命令" / Scenario "导入 YAML 文件"
  - Command: `edera entity import test-entities.yaml`
  - Expect: 显示导入统计

- [x] C25 验证 entity export 命令
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Entity export 命令" / Scenario "导出所有 entities"
  - Command: `edera entity export -o output.yaml`
  - Expect: 生成 YAML 文件

- [x] C26 验证 relation list 别名
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Relation CLI 别名（语法糖）" / Scenario "relation list 别名"
  - Command: `edera relation list --from stock:test --to rss:test --type uses-source`
  - Expect: 转换为 entity list 并返回结果

- [x] C27 验证 relation create 别名
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Relation CLI 别名（语法糖）" / Scenario "relation create 别名"
  - Command: `edera relation create --from stock:test --to rss-source:test --type uses-source`
  - Expect: 转换为 entity create，Relation 创建成功

- [x] C28 验证 relation import 别名
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Relation CLI 别名（语法糖）" / Scenario "relation import/export 别名"
  - Command: `edera relation import test-relations.yaml`
  - Expect: 导入 `relations:` YAML 并显示导入统计

### Task 6: 实现 gRPC entity 和 relation services

**Goal**: 实现 gRPC services 支持 Web Console。

**Files**:
- Modify: `proto/edera.proto`
- Create: `packages/core/src/edera_core/grpc_entity_service.py`
- Test: `packages/core/tests/test_grpc_entity_service.py`

**Requirements**:
- 定义 `EntityService` RPC 接口（包含 relation 操作）
- 实现 CRUD、列过滤和 import/export RPC handlers
- RPC 支持传递 `dag_run_id` 上下文
- Relation 操作复用 Entity RPC（type=relation）

#### Checks

- [x] C29 验证 EntityService RPCs
  - Verifies: `specs/ordinary-entity-database-storage/spec.md` / Requirement "Entity CRUD 操作" / Scenario "创建 entity"
  - Command: `pytest packages/core/tests/test_grpc_entity_service.py::test_create_entity_rpc -v`
  - Expect: RPC 调用成功创建 entity

- [x] C30 验证 Entity 列过滤 RPC
  - Verifies: `specs/entity-cli-commands/spec.md` / Requirement "Entity list 命令" / Scenario "通用列过滤"
  - Command: `pytest packages/core/tests/test_grpc_entity_service.py::test_list_with_filters_rpc -v`
  - Expect: RPC 支持传递多个 filter，返回满足条件的 entities

- [x] C31 验证 Relation RPC（复用 Entity）
  - Verifies: `specs/entity-relations-database-storage/spec.md` / Requirement "Entity relations 存储到数据库" / Scenario "创建 relation"
  - Command: `pytest packages/core/tests/test_grpc_entity_service.py::test_create_relation_via_entity_rpc -v`
  - Expect: 通过 EntityService 创建 type=relation 的 entity

### Task 7: 更新集成测试

### Task 7: 更新集成测试

**Goal**: 更新所有依赖 entities.yaml 和 entity-relations.yaml 的测试。

**Files**:
- Modify: `packages/core/tests/test_*.py`
- Create: `packages/core/tests/fixtures/entity_fixtures.py`

**Requirements**:
- 创建测试 fixture，在数据库中准备测试 entities
- 更新所有测试使用数据库 fixture
- 移除对 YAML 文件的依赖

#### Checks

- [x] C32 验证所有测试通过
  - Verifies: `specs/unified-entity-model/spec.md` / Requirement "Entity 统一 CRUD 接口" / Scenario "通过统一接口创建普通 Entity"
  - Command: `pytest packages/core/tests/ -v`
  - Expect: 所有测试通过，无失败或跳过
