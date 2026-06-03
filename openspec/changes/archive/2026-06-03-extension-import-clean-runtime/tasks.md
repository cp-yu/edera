### Task 1: Manifest imports parsing

**Goal**: Add `imports.entities` to extension manifest parsing without making scan write DB entities.

**Files**:
- Modify: `packages/core/src/edera_core/manifest.py`
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Test: `tests/core/test_core_extension_runtime.py`

**Requirements**:
- Parse `imports.entities` as POSIX paths relative to the extension root.
- Reject absolute paths and parent traversal.
- Preserve current handlers, entity types, storage and depends behavior.
- Keep `scan_extensions()` read-only for entity instances.

#### Checks

- [x] C1 Verify manifest imports parsing
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Manifest imports declarations" / Scenario "Parse imports entities"
  - Command: `uv run pytest tests/core/test_core_extension_runtime.py`
  - Expect: manifest import paths are present in parsed bootstrap metadata while existing extension registry tests still pass

- [x] C2 Verify invalid import path rejection
  - Verifies: `specs/extension-entity-imports/spec.md` / Requirement "Extension manifest entity imports" / Scenario "Reject invalid import path"
  - Command: `uv run pytest tests/core/test_core_extension_runtime.py`
  - Expect: absolute or parent traversal import paths are rejected

### Task 2: Extension import index and importer

**Goal**: Persist import records and import manifest-declared Entity YAML exactly once.

**Files**:
- Create: `packages/core/src/edera_core/extension_imports.py`
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/storage/database.py`
- Modify: `packages/core/src/edera_core/storage/repository.py`
- Test: `tests/core/unit/test_extension_entity_imports.py`

**Requirements**:
- Add `extension_imports` table with import path, entity ref, digest, status and timestamps.
- Import complete Entity YAML files through existing core/ordinary entity repository paths.
- Skip already recorded import paths.
- Record `skipped_existing` without overwriting existing DB entities.
- Store digests needed for future uninstall decisions.

#### Checks

- [x] C3 Verify first import records imported
  - Verifies: `specs/extension-entity-imports/spec.md` / Requirement "Extension entity import records" / Scenario "Record imported entity"
  - Command: `uv run pytest tests/core/unit/test_extension_entity_imports.py`
  - Expect: missing entity is saved and `extension_imports.status` is `imported`

- [x] C4 Verify existing entity is not overwritten
  - Verifies: `specs/extension-entity-imports/spec.md` / Requirement "Extension entity import records" / Scenario "Record existing entity without overwrite"
  - Command: `uv run pytest tests/core/unit/test_extension_entity_imports.py`
  - Expect: existing DB entity remains unchanged and import record status is `skipped_existing`

- [x] C5 Verify repeated import skips
  - Verifies: `specs/extension-entity-imports/spec.md` / Requirement "Extension entity imports are idempotent" / Scenario "Skip already imported path"
  - Command: `uv run pytest tests/core/unit/test_extension_entity_imports.py`
  - Expect: second import does not read path content into DB or overwrite the entity

### Task 3: Clean runtime default generation and startup run

**Goal**: Remove core-generated DAG runs and core-generated default cron triggers.

**Files**:
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Test: `tests/core/test_event_control_service.py`
- Test: `tests/core/integration/test_per_dag.py`

**Requirements**:
- Remove startup `start_run("startup")`.
- Remove `_ensure_default_cron_triggers()` behavior.
- Remove `_default_trigger_entities()` behavior.
- Preserve loading of explicit Trigger Entities.

#### Checks

- [x] C6 Verify controller start is idle
  - Verifies: `specs/dag-control/spec.md` / Requirement "Startup does not run DAG" / Scenario "Controller start is idle"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py`
  - Expect: starting controller creates no DagRun and no active DAG

- [x] C7 Verify no default cron generation
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "Core runtime does not generate configuration entities" / Scenario "Materialization does not create default cron trigger"
  - Command: `uv run pytest tests/core/test_event_control_service.py tests/core/integration/test_per_dag.py`
  - Expect: DAG presence alone does not create `<dag>-default-cron`

- [x] C8 Verify explicit trigger still loads
  - Verifies: `specs/db-backed-core-entities/spec.md` / Requirement "Core runtime does not generate configuration entities" / Scenario "Explicit trigger remains loaded"
  - Command: `uv run pytest tests/core/test_event_control_service.py`
  - Expect: explicit cron trigger from DB/config remains in TriggerExecutor/CronEmitter

### Task 4: Unified manual run dispatch and source model

**Goal**: Route manual DAG runs through emit and remove `startup` from DagRun source.

**Files**:
- Modify: `packages/core/src/edera_core/server.py`
- Modify: `packages/core/src/edera_core/storage/entities.py`
- Modify: `packages/core/src/edera_core/trigger.py`
- Test: `packages/core/tests/test_grpc_control_services.py`
- Test: `tests/core/unit/test_trigger_system.py`

**Requirements**:
- `DagService.Run` emits `manual:dag:<name>` with payload.
- Manual emit directly fires DAG target and does not set EventGroup bit.
- Resulting DagRun source remains `manual`.
- `startup` source is rejected.

#### Checks

- [x] C9 Verify DagService run emits manual event
  - Verifies: `specs/dag-control/spec.md` / Requirement "Manual DAG run uses emit path" / Scenario "DagService run emits manual event"
  - Command: `uv run pytest packages/core/tests/test_grpc_control_services.py`
  - Expect: DagService.Run reaches controller emit path with `manual:dag:<name>` and preserves payload

- [x] C10 Verify manual emit does not set bit
  - Verifies: `specs/dag-control/spec.md` / Requirement "Manual DAG run uses emit path" / Scenario "Manual emit does not set event bit"
  - Command: `uv run pytest tests/core/unit/test_trigger_system.py`
  - Expect: manual emit fires DAG without persisting an EventGroup bit

- [x] C11 Verify startup source rejected
  - Verifies: `specs/data-models/spec.md` / Requirement "DagRun 数据模型" / Scenario "startup source rejected"
  - Command: `uv run pytest tests/core/unit/test_entity_payload.py packages/core/tests/test_grpc_control_services.py`
  - Expect: `DagRun(source="startup")` is rejected and manual/retry/trigger sources remain valid

### Task 5: Remove default-only web routes

**Goal**: Delete hard-coded `default` BFF routes and rely on parameterized DAG routes.

**Files**:
- Modify: `packages/core/src/edera_core/web/routes.py`
- Test: `tests/core/integration/test_per_dag.py`
- Test: `packages/core/tests/test_web_routes.py`

**Requirements**:
- Remove separate `/api/dags/default/run` route handler.
- Remove separate `/api/dags/default/stop` route handler.
- Remove default-only node history route.
- Keep parameterized DAG run/stop/history routes.

#### Checks

- [x] C12 Verify default run uses parameterized route
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "No hard-coded default DAG routes" / Scenario "Run default through parameterized route"
  - Command: `uv run pytest packages/core/tests/test_web_routes.py tests/core/integration/test_per_dag.py`
  - Expect: `POST /api/dags/default/run` is served by the generic DAG route and still works

- [x] C13 Verify no default-only history route
  - Verifies: `specs/edera-web-bff/spec.md` / Requirement "No hard-coded default DAG routes" / Scenario "No default-only node history route"
  - Command: `uv run pytest packages/core/tests/test_web_routes.py`
  - Expect: node history requires a DAG name and no route hard-codes `dag_name = "default"`
