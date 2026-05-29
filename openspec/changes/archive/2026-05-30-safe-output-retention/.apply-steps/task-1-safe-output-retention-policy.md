# Task 1: Safe output retention policy - Detailed TDD Steps

## Context

Goal: Let output retention cleanup run only after a full DAG run finishes successfully, and set the default retention window to 720 hours.

Files:
- `config/system.toml`
- `packages/core/src/edera_core/config/schema.py`
- `packages/core/src/edera_core/dag_controller.py`
- `tests/core/integration/test_per_dag.py`

Requirements:
- `retention_hours` default is 720.
- Current project `config/system.toml` uses `retention_hours = 720`.
- Full successful DAG runs trigger retention cleanup.
- Failed or cancelled runs do not trigger retention cleanup.
- Single-node runs and partial retries do not trigger retention cleanup.

Related Spec: `openspec/changes/safe-output-retention/specs/entity-storage-tiers/spec.md`

## TDD Cycle 1

### Step 1: Write Failing Test

In `tests/core/integration/test_per_dag.py`, add this import with the other imports:

```python
import edera_core.dag_controller as dag_controller_module
from edera_core.errors import DagError
```

In `_write_dag_config`, change the emitted config to use `retention_hours = 720`:

```python
        f'retention_count = 20\nretention_hours = 720\n'
```

Add this helper near the existing test helpers:

```python
def _write_retention_policy_dag(path: Path, *, fail_source: bool = False, slow_source: bool = False) -> Path:
    extensions_dir = path / "extensions"
    _write_retention_extension(extensions_dir)
    (path / "nodes" / "retention-source.yaml").write_text(
        "name: retention-source\n"
        "type: function\n"
        "handler: retention-source\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (path / "nodes" / "retention-sink.yaml").write_text(
        "name: retention-sink\n"
        "type: function\n"
        "handler: retention-sink\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    source_config = ""
    if fail_source or slow_source:
        source_config = (
            "  config:\n"
            "    parameters:\n"
            f"      fail: {str(fail_source).lower()}\n"
            f"      slow: {str(slow_source).lower()}\n"
        )
    (path / "dags" / "default.yaml").write_text(
        "name: default\n"
        "nodes:\n"
        "- id: source\n"
        "  type: retention-source\n"
        f"{source_config}"
        "- id: sink\n"
        "  type: retention-sink\n"
        "edges:\n"
        "- from: source\n"
        "  to: sink\n"
        encoding="utf-8",
    )
    return extensions_dir
```

Add these tests after the retry tests:

```python
@pytest.mark.asyncio
async def test_full_successful_dag_run_triggers_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path, slow_source=True)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await ctrl.run_now("manual", "default")
    finally:
        await ctrl.shutdown()

    assert calls == [(20, 720)]


@pytest.mark.asyncio
async def test_failed_dag_run_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path, fail_source=True)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        with pytest.raises(DagError, match="all source nodes failed"):
            await ctrl.run_now("manual", "default")
    finally:
        await ctrl.shutdown()

    assert calls == []


@pytest.mark.asyncio
async def test_cancelled_dag_run_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        run_id = await ctrl.start_run("manual", "default")
        assert run_id
        await asyncio.sleep(0)
        await ctrl.stop_current("default")
    finally:
        await ctrl.shutdown()

    assert calls == []


@pytest.mark.asyncio
async def test_single_node_run_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await ctrl.run_node_trigger("source", {"manual": True})
        await ctrl.active_runs["default"].task
    finally:
        await ctrl.shutdown()

    assert calls == []


@pytest.mark.asyncio
async def test_partial_retry_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await ctrl.run_now("manual", "default")
        async with ctrl._factory()() as session:
            await store_node_output_entities(session, "original", "source", "analysis", {"summary": "old"}, None)
            await session.commit()
        calls.clear()
        result = await ctrl.retry_node("default", None, ["sink"], "single")
        await ctrl.active_runs["default"].task
    finally:
        await ctrl.shutdown()

    assert result.retry_nodes == ["sink"]
    assert calls == []
```

Add this helper near the extension helper functions:

```python
def _write_retention_extension(path: Path) -> None:
    source = path / "retention-source"
    source.mkdir(parents=True)
    source.joinpath("handler.py").write_text(
        "import asyncio\n"
        "async def run(ctx):\n"
        "    if ctx.params.get('slow'):\n"
        "        await asyncio.sleep(1)\n"
        "    if ctx.params.get('fail'):\n"
        "        raise ValueError('source failed')\n"
        "    return {'manual': True, 'source': ctx.run_id}\n",
        encoding="utf-8",
    )
    sink = path / "retention-sink"
    sink.mkdir(parents=True)
    sink.joinpath("handler.py").write_text(
        "async def run(ctx):\n"
        "    if ctx.params.get('fail'):\n"
        "        raise ValueError('sink failed')\n"
        "    return {'sink': ctx.input.payload}\n",
        encoding="utf-8",
    )
```

### Step 2: Run Test (Verify Fails)

Command:

```bash
uv run pytest tests/core/integration/test_per_dag.py
```

Expected failure: at least the new retention cleanup trigger tests fail because `_persist_outputs()` is still called before final status calculation and from `_run_single_node()`.

Test MUST fail.

### Step 3: Implement Minimal Code

In `packages/core/src/edera_core/config/schema.py`, change:

```python
    retention_hours: int = Field(default=24, ge=0)
```

to:

```python
    retention_hours: int = Field(default=720, ge=0)
```

In `config/system.toml`, change:

```toml
retention_hours = 24
```

to:

```toml
retention_hours = 720
```

In `packages/core/src/edera_core/dag_controller.py`, move cleanup after status calculation and guard it:

```python
            active_outputs = {
                node: output
                for node, output in result.node_outputs.items()
                if retry_nodes is None or node in retry_nodes
            }
            status = "cancelled" if stop_event is not None and stop_event.is_set() else _result_status(active_outputs)
            if retry_nodes is None and status == "succeeded":
                await _persist_outputs(
                    factory,
                    config.system.retention_count,
                    config.system.retention_hours,
                )
            _cleanup_sandboxes(config)
```

Remove the unconditional `_persist_outputs(...)` call from `_run_single_node()`.

### Step 4: Run Test (Verify Passes)

Command:

```bash
uv run pytest tests/core/integration/test_per_dag.py
```

Expected pass: all tests in `tests/core/integration/test_per_dag.py` pass.

Test MUST pass.

### Step 5: Commit

```bash
git add config/system.toml packages/core/src/edera_core/config/schema.py packages/core/src/edera_core/dag_controller.py tests/core/integration/test_per_dag.py openspec/changes/safe-output-retention/.apply-isolation.json openspec/changes/safe-output-retention/.apply-steps/task-1-safe-output-retention-policy.md
git commit -m "fix: apply safe output retention policy"
```

## Summary

Total cycles: 1

Modified files:
- `config/system.toml`
- `packages/core/src/edera_core/config/schema.py`
- `packages/core/src/edera_core/dag_controller.py`
- `tests/core/integration/test_per_dag.py`
- `openspec/changes/safe-output-retention/.apply-isolation.json`
- `openspec/changes/safe-output-retention/.apply-steps/task-1-safe-output-retention-policy.md`

Commit count: 1
