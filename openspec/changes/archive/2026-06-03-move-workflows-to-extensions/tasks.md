### Task 1: Default news workflow package

**Goal**: Create the extension package that owns and imports the default news workflow.

**Files**:
- Create: `extensions/default-news-workflow/manifest.yaml`
- Create: `extensions/default-news-workflow/entities/dags/default.yaml`
- Create: `extensions/default-news-workflow/entities/nodes/*.yaml`
- Create: `extensions/default-news-workflow/entities/triggers/default-default-cron.yaml`
- Create: `extensions/default-news-workflow/entities/sources/*.yaml`
- Test: `tests/extensions/test_default_news_workflow.py`

**Requirements**:
- Manifest declares handler provider dependencies for all default workflow node types.
- Manifest explicitly lists every owned Entity file in `imports.entities`.
- Imported `default` DAG preserves the 6-node, 5-edge topology.
- Imported source seed Entity records cover only sources directly referenced by the DAG.
- Imported trigger keeps the existing cron expression and target.

#### Checks

- [x] C1 Verify default workflow manifest imports
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default news workflow extension package" / Scenario "Manifest declares workflow imports"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py`
  - Expect: manifest imports include default DAG, nodes, trigger and source seed Entity files with no implicit directory import

- [x] C2 Verify default workflow dependencies
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default news workflow extension package" / Scenario "Dependencies are declared"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py`
  - Expect: bootstrap accepts the package only when required provider extensions are present

- [x] C3 Verify imported default DAG topology
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default DAG topology is preserved" / Scenario "Imported default DAG loads"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py`
  - Expect: imported `default` DagGraph has 6 nodes, 5 edges and the expected node types

- [x] C4 Verify default source seeds
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default workflow seed sources are extension-owned" / Scenario "Source seeds imported with workflow"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py`
  - Expect: imported DB contains `rss-source:hn-rss` and the five API source Entity records

### Task 2: UZI-Skill workflow package imports

**Goal**: Move the UZI-Skill workflow-owned runtime entities into `extensions/uzi-skill/`.

**Files**:
- Modify: `extensions/uzi-skill/manifest.yaml`
- Create: `extensions/uzi-skill/entities/dags/uzi-skill-analysis.yaml`
- Create: `extensions/uzi-skill/entities/nodes/uzi-*.yaml`
- Create: `extensions/uzi-skill/entities/triggers/uzi-skill-analysis-default-cron.yaml`
- Create: `extensions/uzi-skill/entities/resources/v8_isolate.yaml`
- Test: `tests/extensions/test_uzi_skill_dag.py`

**Requirements**:
- Keep `legacy-script-adapter` handler registration.
- Manifest explicitly imports UZI DAG, UZI node definitions, cron trigger and `v8_isolate`.
- Imported UZI DAG preserves topology, aliases, optional fetchers/renderers and fan-in modes.
- Imported trigger keeps the existing cron expression and target.
- Imported `v8_isolate` resource has `permits: 1`.

#### Checks

- [x] C5 Verify UZI manifest imports
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill workflow extension imports" / Scenario "Manifest imports UZI workflow entities"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py`
  - Expect: manifest imports include UZI DAG, UZI nodes, UZI trigger and `v8_isolate` while `legacy-script-adapter` remains registered

- [x] C6 Verify imported UZI topology
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "DAG 拓扑声明" / Scenario "DAG 配置可加载"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py`
  - Expect: imported `uzi-skill-analysis` DagGraph contains all declared nodes and edges without load errors

- [x] C7 Verify UZI resource import
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill workflow extension imports" / Scenario "Resource entity imported"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py`
  - Expect: imported DB contains Resource Entity `v8_isolate` with `permits` equal to 1

- [x] C8 Verify UZI trigger import
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill trigger is imported" / Scenario "Imported UZI trigger targets DAG"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py`
  - Expect: Trigger registry includes `uzi-skill-analysis-default-cron` targeting `dag:uzi-skill-analysis`

### Task 3: Top-level config boundary cleanup

**Goal**: Remove migrated workflow instances from top-level runtime config sources.

**Files**:
- Modify: `config/dags/`
- Modify: `config/nodes/`
- Modify: `config/triggers/`
- Modify: `config/entities.yaml`
- Test: `tests/core/unit/test_entities_config.py`
- Test: `tests/extensions/test_default_news_workflow.py`
- Test: `tests/extensions/test_uzi_skill_dag.py`

**Requirements**:
- Remove or runtime-ignore migrated default DAG, node and trigger files.
- Remove or runtime-ignore migrated UZI DAG, node, trigger and `v8_isolate` top-level entries.
- Keep stock Entity and entity relation seed data outside workflow packages.
- Keep config schemas and skills outside this migration.

#### Checks

- [x] C9 Verify default top-level config is not authoritative
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Top-level default workflow config is no longer authoritative" / Scenario "No top-level default DAG source"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py tests/core/unit/test_entities_config.py`
  - Expect: runtime no longer uses top-level `config/dags/default.yaml` as a default workflow source

- [x] C10 Verify UZI top-level config is not authoritative
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "Top-level UZI workflow config is no longer authoritative" / Scenario "No top-level UZI DAG source"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py tests/core/unit/test_entities_config.py`
  - Expect: runtime no longer uses top-level `config/dags/uzi-skill-analysis.yaml` as a UZI workflow source

- [x] C11 Verify stock seeds remain outside default package
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default workflow seed sources are extension-owned" / Scenario "Stock seeds remain outside package"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py`
  - Expect: `default-news-workflow` imports do not include stock Entity or entity relation seed files

### Task 4: Workflow package import runtime integration

**Goal**: Prove the migrated packages work through extension imports and DB-backed runtime loading.

**Files**:
- Modify: `packages/core/src/edera_core/bootstrap.py`
- Modify: `packages/core/src/edera_core/config/loader.py`
- Modify: `packages/core/src/edera_core/dag_controller.py`
- Test: `tests/core/test_core_extension_runtime.py`
- Test: `tests/core/integration/test_per_dag.py`
- Test: `tests/extensions/test_default_news_workflow.py`

**Requirements**:
- Workflow package imports run before DAG registry materialization.
- Runtime resolves migrated DAGs from DB-backed Entity storage.
- Trigger registry receives imported cron triggers.
- Manual DAG run behavior remains unchanged after migration.
- Manifest scan remains read-only; DB writes happen only through importer.

#### Checks

- [x] C12 Verify workflow import list is explicit
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Workflow package import boundary" / Scenario "Import list is explicit"
  - Command: `uv run pytest tests/core/test_core_extension_runtime.py tests/extensions/test_default_news_workflow.py`
  - Expect: only files listed in `imports.entities` are imported from workflow packages

- [x] C13 Verify default runtime loads imported workflow
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Top-level default workflow config is no longer authoritative" / Scenario "Runtime loads imported default workflow"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py tests/extensions/test_default_news_workflow.py`
  - Expect: runtime materialization resolves `default` from DB-backed Entity storage after imports

- [x] C14 Verify UZI runtime loads imported workflow
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "Top-level UZI workflow config is no longer authoritative" / Scenario "Runtime loads imported UZI workflow"
  - Command: `uv run pytest tests/core/integration/test_per_dag.py tests/extensions/test_uzi_skill_dag.py`
  - Expect: runtime materialization resolves `uzi-skill-analysis` from DB-backed Entity storage after imports

- [x] C15 Verify default trigger cron is preserved
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default workflow trigger is imported" / Scenario "Cron expression preserved"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py tests/core/integration/test_per_dag.py`
  - Expect: `default-default-cron` loads with `cron:"*/30 * * * *"` and `enabled = true`

### Task 5: Migration regression checks

**Goal**: Add focused regressions for topology equivalence, trigger preservation and manifest ownership boundaries.

**Files**:
- Test: `tests/extensions/test_default_news_workflow.py`
- Test: `tests/extensions/test_uzi_skill_dag.py`
- Test: `tests/core/test_core_extension_runtime.py`

**Requirements**:
- Validate default node source configs survive migration.
- Validate UZI topology still passes `topological_layers()`.
- Validate UZI cron expression survives migration.
- Validate moved instances are not duplicated between manifest imports and top-level config.

#### Checks

- [x] C16 Verify default source node configs
  - Verifies: `specs/default-news-workflow/spec.md` / Requirement "Default DAG topology is preserved" / Scenario "Source node configs are preserved"
  - Command: `uv run pytest tests/extensions/test_default_news_workflow.py`
  - Expect: imported `rss-fetcher` and `api-fetcher` configs reference the same source refs as before migration

- [x] C17 Verify UZI topological validation
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "DAG 拓扑声明" / Scenario "拓扑验证通过"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py`
  - Expect: imported UZI DagGraph passes `topological_layers()` with no cycle and all nodes reachable

- [x] C18 Verify UZI cron expression
  - Verifies: `specs/uzi-skill-dag-instance/spec.md` / Requirement "UZI-Skill trigger is imported" / Scenario "UZI cron expression preserved"
  - Command: `uv run pytest tests/extensions/test_uzi_skill_dag.py`
  - Expect: `uzi-skill-analysis-default-cron` loads with `cron:"*/30 * * * *"` and `enabled = true`

- [x] C19 Verify moved config is not duplicated
  - Verifies: `specs/extension-manifest-system/spec.md` / Requirement "Workflow package import boundary" / Scenario "Top-level config is not duplicated"
  - Command: `uv run pytest tests/core/test_core_extension_runtime.py tests/extensions/test_default_news_workflow.py tests/extensions/test_uzi_skill_dag.py`
  - Expect: migrated DAG/node/trigger/resource instances are owned by workflow manifest imports, not duplicated as top-level runtime config
