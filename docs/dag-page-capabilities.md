# DAG Page Capabilities (Unified Workbench)

> Finalized 2026-05-16 via `/grill-me` session.

## Core Positioning

- **Single DAG** as the primary object.
- DAG switch → topology, node config, run state all refresh to the selected DAG.
- **No "total save" button** — configuration types are saved separately.

## Configuration Responsibilities & Save Model

| Type | Allowed in DAG page | Save behavior |
|------|---------------------|---------------|
| DAG topology (nodes/edges/groups) | ✅ Full control | Separate save to `config/dags/*.yaml` |
| Node definition (Fetcher Instance runtime parameters) | ✅ Editable | Separate save to `config/nodes/*.yaml` (global, affects all DAGs that reference it) |
| Source Definition (new `type` like `fetch-api`) | ❌ Forbidden | Advanced config page only |
| Source Instance (new RSS/Web URL under existing `type`) | ✅ Inline quick-create | Immediately writes to `portfolio.yaml`, then backfills current fetcher |
| Run control (Run/Stop/Status) | ✅ For current DAG | Separate trigger, not bound to config saves |

## Node Editing Rules

**Editable (runtime parameters):**
- `name`, `source_names`, `timeout_seconds`, `parameters`

**Read-only (identity/contract fields):**
- `type`, `skills`, `input_type`, `output_type`

On save: must warn "this node is global — changes affect all DAGs that use it".

## Creating a New Fetcher Instance

**Methods:**
- **Copy from existing** (primary workflow)
- **Skeleton creation** (RSS Fetcher / Web Fetcher)

**Skeleton presets:**
- `type=function`, `skills=fetch-rss` or `fetch-web`, `input_type=Any`, `output_type=list[RawItem]`

**Name:** auto-suggested (e.g., `rss-fetcher-1`), user-editable, globally unique enforced on save.

**After creation:** automatically added to current DAG canvas and selected.

## Inline Creation of Source Instance (RSS/Web URL)

- Triggered from fetcher inspector: "+ New Input Source"
- Minimal form: only `name` + `url`
- `type` fixed to current fetcher's type (rss/web) — not user-selectable
- **Must bind to at least one target** (default: all targets involved in current DAG; user can adjust)
- On save: writes to `portfolio.yaml` → then backfills `source_names` of current fetcher and remains checked

## Run Control

- Run/Stop/Status bound to **currently selected DAG**
- Status display logic: show **current running** if any; otherwise **latest run** for that DAG
- Requires backend API change from global to per‑DAG status

## Canvas Presentation Model (No UI Groups)

**No shared/stock group boxes** on canvas.

**Node colors:**
- Single target → color of that target
- Multiple targets → RGB average + border

**Filtering:**
- Multi‑select dropdown of targets
- Canvas shows nodes that intersect **at least one** selected target
- Node appears once; visibility controlled by filter

## Node Addition to Canvas

- Drag from existing node list → adds reference to current DAG
- Newly created fetcher instance → auto‑added and selected

## Terminology (EN/CN)

| English | Chinese | Storage / Notes |
|---------|---------|----------------|
| Source Definition | 信息源定义 | `portfolio.yaml` → `sources` (type/url/regex) |
| Source Instance | 信息源实例 | A specific entry under `sources` (e.g., `sample-rss`) |
| Fetcher Instance | 采集器实例 | `config/nodes/*.yaml` |
| DAG Topology | DAG 拓扑 | `config/dags/*.yaml` |
| Target | 标的 | `portfolio.yaml` → `targets` |

## Out of Scope for DAG Page

- Creating/editing Source Definitions (new `type`)
- Creating/editing Target definitions
- Bulk configuration of portfolios
- Source Definition → Target binding (happens elsewhere; only consumption here)

---

**Implementation reference:** Use this document as the specification for all DAG page changes. Open questions or clarifications should trace back to a decision recorded here.
