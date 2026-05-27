# Sub-DAG Runtime Context Risk

## Problem

Sub-DAG execution currently maps only the parent node payload into the child DAG. Parent `NodeInput.metadata` is not passed into the child run.

This is acceptable for now, but it is a known risk for degraded or partially failed parent runs. If a parent DAG reaches a sub-DAG after optional upstream failures, child nodes cannot see those parent upstream failures unless the information was manually embedded in payload.

## Evidence

- `DagRunner._execute_sub_dag()` calls `_mapped_input(node_input.payload, input_mapping)` and starts the child run with that payload.
- The same path does not pass `node_input.metadata` into `runner.run(...)`.
- Child DAG results can return `sub_dag_failures` to the parent, but parent context does not flow into the child.

## Impact

Moving existing nodes into a sub-DAG can change behavior:

- Function nodes inside the sub-DAG lose parent failure context from `ctx.input.metadata`.
- Agent nodes inside the sub-DAG cannot be told about parent degraded state through runtime context.
- Downstream reporting nodes may omit parent `failed_sources`, degraded status, or upstream failure explanations.

## Deferred Decision

Do not solve this in the current optional-edge fix. Track it as a separate core design issue.

Recommended future direction:

- Keep business payload type-clean.
- Pass parent runtime context to child DAGs under a namespaced field such as `parent_context`.
- Do not flatten parent metadata into child metadata, because child-local `upstreams`, `failures`, and `warnings` must remain distinguishable.
