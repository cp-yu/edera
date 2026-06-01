### Task 1: Core entity database schema

**Goal**: Create DB schema and repository primitives for core DB-backed Entity types.

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/storage/database.py`
- Create: `alembic/versions/<revision>_db_backed_core_entities.py`
- Test: `tests/core/unit/test_entity_crud.py`

**Requirements**:
- Create `entity_types`, `entity_node`, `entity_dag`, `entity_trigger`, `entity_resource`, and `log_index`.
- Fully columnize current core fields for `node`, `dag`, `trigger`, and `resource`.
- Keep output entities in `node_outputs`.
- Preserve UUID and business_id lookup semantics.

#### Checks

- [x] C1 Verify core tables exist
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心 Entity 固定 per-type tables" / Scenario "核心字段列化"
  - Command: `uv run pytest tests/core/unit/test_entity_crud.py`
  - Expect: tests prove core Entity rows persist through per-type tables and core fields do not require `attributes_json`

- [x] C2 Verify output table separation
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心 Entity 固定 per-type tables" / Scenario "核心表与输出表分离"
  - Command: `uv run pytest tests/core/integration/test_results_api.py`
  - Expect: output Entity queries still use `node_outputs`

### Task 2: DB-backed EntityStore and EntityService

**Goal**: Route core Entity CRUD/query through DB-backed storage from server and clients.

**Files**:
- Modify: `packages/core/src/edera_core/config/entities.py`
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Modify: `proto/edera.proto`
- Test: `tests/core/unit/test_entity_crud.py`

**Requirements**:
- `EntityService` create/get/list/update/delete/query uses DB for core Entity types.
- Core EntityType metadata is read from DB-backed `entity_types`.
- Permission checks continue to run server-side.
- YAML/config files are not used as runtime source of truth for core types.

#### Checks

- [x] C3 Verify DB source of truth through gRPC
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心配置型 Entity 使用 DB source of truth" / Scenario "运行时从 DB 读取核心 Entity"
  - Command: `uv run pytest tests/core/unit/test_entity_crud.py tests/core/unit/test_cli.py`
  - Expect: EntityService returns DB-backed node/dag/trigger/resource data without reading YAML runtime files

- [x] C4 Verify EntityType metadata
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "EntityType DB 元数据" / Scenario "读取核心 EntityType 元数据"
  - Command: `uv run pytest tests/core/unit/test_entity_types.py`
  - Expect: business_id and display metadata resolve from DB-backed metadata

### Task 3: YAML import, export, and template CLI

**Goal**: Provide full Entity YAML file workflows for CLI and server.

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `proto/edera.proto`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- Add `edera entity import --file`.
- Add `edera entity export <ref> --file`.
- Add `edera entity template --type <type> --file`.
- Use full Entity YAML document format with `type`, `id`, and `attributes`.
- Reject invalid YAML or missing required fields.

#### Checks

- [x] C5 Verify YAML import/export/template
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Entity YAML 文件工作流" / Scenario "Export template from entity type"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: template output can be edited, imported, and exported in the same full Entity YAML format

- [x] C6 Verify invalid import rejection
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Entity YAML 文件工作流" / Scenario "Reject invalid import file"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: malformed or incomplete YAML import exits non-zero with validation error

### Task 4: Runtime snapshot migration

**Goal**: Build committed runtime snapshots from DB-backed core Entities and stop runtime YAML loading.

**Files**:
- Modify: `packages/core/src/edera_core/config/loader.py`
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Modify: `packages/core/src/edera_core/hot_reload.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/unit/test_hot_reload.py`

**Requirements**:
- Runtime snapshot reads `node`, `dag`, `trigger`, and `resource` from DB.
- Snapshot replacement remains committed/transactional.
- Failed reload keeps old snapshot.
- YAML files remain only import/export/template artifacts.

#### Checks

- [x] C7 Verify committed snapshot replacement
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "核心配置型 Entity 使用 DB source of truth" / Scenario "DB 写入后替换 committed snapshot"
  - Command: `uv run pytest tests/core/unit/test_hot_reload.py tests/core/unit/test_server_hot_reload.py`
  - Expect: DB-backed config changes replace snapshot only after successful validation

- [x] C8 Verify runtime no longer reads core YAML
  - Verifies: `specs/entity-storage-tiers/spec.md` / Requirement "三层存储模型" / Scenario "核心配置型 Entity 存储在数据库 per-type table"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py`
  - Expect: DAG runner can execute from DB-backed core Entities without runtime YAML source files

## Remediation

- [x] [code_fix] Runtime/control paths still read core DAG YAML/config as source of truth. Replace hot reload and DAG control runtime checks with DB-backed committed snapshot reads.
- [x] [code_fix] Runtime startup/snapshot construction still seeds core Entities from YAML/config. Replace runtime materialization with DB-only reads for `node`, `dag`, `trigger`, and `resource`.
- [x] [code_fix] DAG/node graph control mutations still write core YAML. Route GraphService DAG/node mutations through DB-backed core Entity writes and committed snapshot refresh.

### Task 5: Runtime facts and log index boundary

**Goal**: Preserve in-memory runtime state semantics while adding file-backed raw log indexing.

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/dag/runner.py`
- Test: `tests/core/unit/test_node_executor.py`

**Requirements**:
- Active scheduling state remains in memory.
- Runtime tables persist committed facts only.
- Raw stdout/stderr logs are written to session files.
- `log_index` stores path, digest, size, run_id, node_id, and timestamps.

#### Checks

- [x] C9 Verify runtime facts remain projections
  - Verifies: `specs/runtime-input-context/spec.md` / Requirement "Runtime facts storage model" / Scenario "Active runtime state stays in memory"
  - Command: `uv run pytest tests/core/integration/test_dag_runner.py`
  - Expect: runtime tables contain committed facts while scheduling behavior still follows in-memory runner state

- [x] C10 Verify raw log index
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "Raw log 文件索引" / Scenario "Raw log 文件落盘"
  - Command: `uv run pytest tests/core/unit/test_node_executor.py`
  - Expect: raw logs are file-backed and queryable through `log_index` metadata
