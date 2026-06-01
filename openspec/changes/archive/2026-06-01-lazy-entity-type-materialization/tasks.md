### Task 1: EntityType materialization metadata

**Goal**: Extend ordinary EntityType metadata for per-type tables and materialized field lifecycle.

**Files**:
- Modify: `packages/core/src/edera_core/config/schema.py`
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `tests/core/unit/test_entity_types.py`

**Requirements**:
- Record table mapping for ordinary EntityTypes.
- Record materialized fields with type and index intent.
- Record deprecated fields.
- Preserve core type fixed-table behavior from phase 1.

#### Checks

- [x] C1 Verify metadata fields
  - Verifies: `specs/entity-system/spec.md` / Requirement "实体类型定义" / Scenario "Materialized fields metadata"
  - Command: `uv run pytest tests/core/unit/test_entity_types.py`
  - Expect: ordinary EntityType metadata stores materialized and deprecated field state

### Task 2: Ordinary per-type table storage

**Goal**: Store ordinary EntityType instances in `entity_<type>` tables with `attributes_json`.

**Files**:
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Modify: `packages/core/src/edera_core/config/entities.py`
- Test: `tests/core/unit/test_entity_crud.py`

**Requirements**:
- Create/register ordinary `entity_<type>` tables.
- Include `id`, `business_id`, `schema_version`, `attributes_json`, `created_at`, and `updated_at`.
- Store unmaterialized fields in `attributes_json`.
- Do not alter core fixed tables.

#### Checks

- [x] C2 Verify ordinary table creation
  - Verifies: `specs/lazy-entity-type-materialization/spec.md` / Requirement "普通 EntityType per-type table" / Scenario "Create ordinary entity type table"
  - Command: `uv run pytest tests/core/unit/test_entity_crud.py`
  - Expect: ordinary EntityType instances persist in their own table with `attributes_json`

- [x] C3 Verify core tables unchanged
  - Verifies: `specs/lazy-entity-type-materialization/spec.md` / Requirement "普通 EntityType per-type table" / Scenario "Core tables unchanged"
  - Command: `uv run pytest tests/core/unit/test_entity_crud.py`
  - Expect: node/dag/trigger/resource fixed table behavior is unaffected

### Task 3: Lazy materialization engine

**Goal**: Add explicit plan/apply support for materializing ordinary fields into real columns.

**Files**:
- Create: `packages/core/src/edera_core/storage/materialization.py`
- Modify: `packages/core/src/edera_core/storage/database.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `tests/core/unit/test_entity_crud.py`

**Requirements**:
- Plan DDL and backfill for one field.
- Apply materialized column creation and optional index creation.
- Backfill existing values from `attributes_json`.
- Query materialized fields through real columns.

#### Checks

- [x] C4 Verify materialized field apply
  - Verifies: `specs/lazy-entity-type-materialization/spec.md` / Requirement "Lazy materialization" / Scenario "Materialize indexed field"
  - Command: `uv run pytest tests/core/unit/test_entity_crud.py`
  - Expect: field is added as a real column, indexed when requested, and historical data is backfilled

- [x] C5 Verify materialized query path
  - Verifies: `specs/lazy-entity-type-materialization/spec.md` / Requirement "Lazy materialization" / Scenario "Query materialized field"
  - Command: `uv run pytest tests/core/unit/test_entity_crud.py`
  - Expect: query uses the materialized column before falling back to `attributes_json`

### Task 4: Deprecated field lifecycle

**Goal**: Support deprecated field metadata and delayed cleanup for ordinary EntityTypes.

**Files**:
- Modify: `packages/core/src/edera_core/config/entities.py`
- Modify: `packages/core/src/edera_core/storage/materialization.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `tests/core/unit/test_entity_types.py`

**Requirements**:
- Mark fields as deprecated.
- Stop new writes to deprecated fields.
- Keep old columns until cleanup.
- Provide cleanup guardrails for unused deprecated columns.

#### Checks

- [x] C6 Verify deprecated write behavior
  - Verifies: `specs/lazy-entity-type-materialization/spec.md` / Requirement "Deprecated field lifecycle" / Scenario "Stop using deprecated field"
  - Command: `uv run pytest tests/core/unit/test_entity_types.py`
  - Expect: deprecated fields are not populated on new writes and existing columns are not dropped immediately

- [x] C7 Verify cleanup guardrail
  - Verifies: `specs/lazy-entity-type-materialization/spec.md` / Requirement "Deprecated field lifecycle" / Scenario "Cleanup deprecated column"
  - Command: `uv run pytest tests/core/unit/test_entity_types.py`
  - Expect: cleanup only proceeds after metadata confirms the field is no longer accessed

### Task 5: CLI and DDL namespace integration

**Goal**: Expose materialization maintenance commands and keep EntityType tables separate from extension tables.

**Files**:
- Modify: `packages/core/src/edera_core/cli.py`
- Modify: `packages/core/src/edera_core/grpc_client.py`
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Test: `tests/core/unit/test_cli.py`

**Requirements**:
- Add materialize plan/apply/inspect commands.
- Commands call server through gRPC.
- Entity tables use `entity_` namespace.
- Extension tables continue using `ext_` namespace.

#### Checks

- [x] C8 Verify materialization CLI
  - Verifies: `specs/edera-cli/spec.md` / Requirement "Entity materialization maintenance commands" / Scenario "Plan field materialization"
  - Command: `uv run pytest tests/core/unit/test_cli.py`
  - Expect: CLI returns planned column, index, and backfill summary through gRPC

- [x] C9 Verify namespace separation
  - Verifies: `specs/extension-declarative-storage/spec.md` / Requirement "Entity table DDL namespace compatibility" / Scenario "Entity and extension table names do not collide"
  - Command: `uv run pytest tests/core/test_core_extension_runtime.py`
  - Expect: `entity_` and `ext_` tables coexist without name collision
