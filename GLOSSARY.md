# Edera Glossary

## Canonical Terms

| Term | Definition | Do Not Use |
| --- | --- | --- |
| DAG | Directed acyclic graph that defines executable node topology. | ~~Pipeline~~ |
| Node | Executable DAG vertex backed by a node type and instance config. | Task, step |
| Edge | Directed dependency from one node to another. | Link |
| Run | One execution instance of a DAG or node-scoped retry/resume flow. | Cycle |
| run_id | Stable identifier for one Run across storage, API, CLI, and UI. | cycle_id |
| Trigger Entity | Entity of type `trigger` containing `wait_for`, `target`, and `enabled`. | RPC trigger verb |
| TriggerExecutor | Runtime component that evaluates Trigger Entities and fires targets. | Trigger |
| Emit | Inject or record an event into the event/trigger system. | Trigger |
| Source | Audit origin for a DagRun, such as `manual`, `startup`, `retry`, or `trigger:<id>`. | trigger column |

## Verb Conventions

| Action | API | CLI |
| --- | --- | --- |
| Run a DAG manually | `DagService.Run` | `edera dag run <dag>` |
| Emit an event | `EventService.Emit` | `edera event emit <event>` |
| Pause scheduler | `SystemService.PauseScheduler` | `edera system pause-scheduler` |
| Resume scheduler | `SystemService.ResumeScheduler` | `edera system resume-scheduler` |
| Query scheduler status | `SystemService.SchedulerStatus` | `edera system scheduler-status` |
| Stop a DAG | `DagService.Stop` | `edera dag stop <dag>` |
| Retry DAG nodes | `DagService.Retry` | `edera dag retry <dag>` |

## Storage Conventions

| Table | Purpose |
| --- | --- |
| `dag_runs` | One row per DAG Run. |
| `node_runs` | Per-node execution status within a Run. |
| `node_outputs` | Persisted output entities produced by nodes. |
| `edge_inputs` | Runtime edge input facts for a Run. |
| `emit_records` | Event injection audit records. |
| `event_group_bits` | Durable event-group bits used by TriggerExecutor. |

`dag_runs.source` accepts `manual`, `startup`, `retry`, or `trigger:<trigger_name>`.

## Sub-DAG Runs

Sub-DAG execution gets an independent `run_id`. Parent-child traceability uses `parent_run_id` in node metadata; do not reuse the parent Run's `run_id` for the child DAG.
