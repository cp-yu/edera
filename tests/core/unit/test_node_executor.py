import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from edera_core.config.entities import EntityStore
from edera_core.config.schema import (
    DagNodeInstance,
    EntitiesConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.dag_controller import _record_raw_log, _record_summary_log
from edera_core.node.executor import NodeExecutor, _apply_instance_config
from edera_core.node.models import NodeContext, NodeInput
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import query_log_index
from edera_types import NodeOutput


def _load_config():
    node_type = EntityTypeConfig.model_validate(
        {
            "display_name": "Node",
            "business_id_field": "name",
            "display_template": "{name}",
            "schema": {
                "required": ["name", "type", "input_type", "output_type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "handler": {"type": "string"},
                    "input_type": {"type": "string"},
                    "output_type": {"type": "string"},
                },
            },
        }
    )
    return SimpleNamespace(
        nodes={
            "rss-fetcher": NodeConfig(
                name="rss-fetcher",
                type="function",
                handler="fetch-rss",
                input_type="Any",
                output_type="Any",
            ),
            "reader": NodeConfig(
                name="reader",
                type="function",
                handler="summarize",
                input_type="Any",
                output_type="Any",
            ),
        },
        system=SystemConfig(),
        runtime=RuntimeSettings(),
        entity_types={"node": node_type},
    )


@pytest.mark.asyncio
async def test_node_executor_function_handler_returns_json_payload() -> None:
    config = _load_config()

    async def handler(node_input: NodeInput) -> dict[str, object]:
        return {"run": node_input.run_id, "value": node_input.payload}

    instance = DagNodeInstance(
        id="0194f7a6-7b17-7c01-b601-100000000001",
        type="rss-fetcher",
        alias="empty-rss-fetcher",
        config={"source_names": []},
    )
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        handlers={"fetch-rss": handler},
        instances={instance.id: instance},
    )
    output = await executor.execute(
        instance.id,
        NodeInput(run_id="run", payload={"source_names": []}),
    )
    assert output.ok
    assert output.payload == {"run": "run", "value": {"source_names": []}}


@pytest.mark.asyncio
async def test_node_executor_records_handler_node_output() -> None:
    recorded: list[tuple[str, str, str, object, str | None]] = []
    summaries: list[tuple[str, str, dict[str, object]]] = []

    async def handler(_node_input: NodeInput) -> NodeOutput:
        return NodeOutput(node_name="report", ok=True, payload={"report_path": "/tmp/report.html"})

    async def recorder(
        run_id: str,
        node_id: str,
        entity_type: str,
        payload: object,
        session_id: str | None,
    ) -> None:
        recorded.append((run_id, node_id, entity_type, payload, session_id))

    async def summary_recorder(run_id: str, node_id: str, summary: dict[str, object]) -> None:
        summaries.append((run_id, node_id, summary))

    node = NodeConfig(
        name="report-node",
        type="function",
        handler="report",
        input_type="Any",
        output_type="Any",
    )
    executor = NodeExecutor(
        {"report-node": node},
        SystemConfig(),
        RuntimeSettings(),
        handlers={"report": handler},
        output_recorder=recorder,
        execution_summary_recorder=summary_recorder,
    )

    output = await executor.execute("report-node", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == {"report_path": "/tmp/report.html"}
    assert recorded == [("run", "report-node", "any", {"report_path": "/tmp/report.html"}, None)]
    assert summaries == [
        (
            "run",
            "report-node",
            {
                "run_id": "run",
                "node_id": "report-node",
                "ok": True,
                "status": "succeeded",
                "error": None,
                "failure_kind": None,
                "payload_empty": False,
                "session_id": None,
                "raw_log_path": None,
            },
        )
    ]


@pytest.mark.asyncio
async def test_node_executor_records_empty_payload_summary_without_output() -> None:
    recorded: list[tuple[str, str, str, object, str | None]] = []
    summaries: list[tuple[str, str, dict[str, object]]] = []

    async def handler(_node_input: NodeInput) -> None:
        return None

    async def output_recorder(
        run_id: str,
        node_id: str,
        entity_type: str,
        payload: object,
        session_id: str | None,
    ) -> None:
        recorded.append((run_id, node_id, entity_type, payload, session_id))

    async def summary_recorder(run_id: str, node_id: str, summary: dict[str, object]) -> None:
        summaries.append((run_id, node_id, summary))

    node = NodeConfig(
        name="empty-node",
        type="function",
        handler="empty",
        input_type="Any",
        output_type="Any",
    )
    executor = NodeExecutor(
        {"empty-node": node},
        SystemConfig(),
        RuntimeSettings(),
        handlers={"empty": handler},
        output_recorder=output_recorder,
        execution_summary_recorder=summary_recorder,
    )

    output = await executor.execute("empty-node", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload is None
    assert recorded == []
    assert summaries[0][2]["payload_empty"] is True


@pytest.mark.asyncio
async def test_node_executor_records_failed_summary_without_output() -> None:
    recorded: list[tuple[str, str, str, object, str | None]] = []
    summaries: list[tuple[str, str, dict[str, object]]] = []

    async def handler(_node_input: NodeInput) -> object:
        raise RuntimeError("boom")

    async def output_recorder(
        run_id: str,
        node_id: str,
        entity_type: str,
        payload: object,
        session_id: str | None,
    ) -> None:
        recorded.append((run_id, node_id, entity_type, payload, session_id))

    async def summary_recorder(run_id: str, node_id: str, summary: dict[str, object]) -> None:
        summaries.append((run_id, node_id, summary))

    node = NodeConfig(
        name="failing-node",
        type="function",
        handler="failing",
        input_type="Any",
        output_type="Any",
    )
    executor = NodeExecutor(
        {"failing-node": node},
        SystemConfig(),
        RuntimeSettings(),
        handlers={"failing": handler},
        output_recorder=output_recorder,
        execution_summary_recorder=summary_recorder,
    )

    output = await executor.execute("failing-node", NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "boom"
    assert recorded == []
    assert summaries[0][2]["ok"] is False
    assert summaries[0][2]["status"] == "failed"
    assert summaries[0][2]["error"] == "boom"


@pytest.mark.asyncio
async def test_node_executor_missing_skill_reports_name(tmp_path: Path) -> None:
    config = _load_config()
    instance = DagNodeInstance(
        id="0194f7a6-7b17-7c01-b601-100000000002",
        type="rss-fetcher",
        alias="missing-handler-fetcher",
        config={"source_names": []},
    )
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        handlers={},
        instances={instance.id: instance},
        handlers_dir=tmp_path,
        skills_dir=tmp_path,
    )
    output = await executor.execute(
        instance.id,
        NodeInput(run_id="run", payload={"source_names": []}),
    )
    assert not output.ok
    assert "fetch-rss" in (output.error or "")


@pytest.mark.asyncio
async def test_node_entity_execution_uses_registry_module_cache(tmp_path: Path) -> None:
    config = _load_config()
    handler = tmp_path / "dynamic.py"
    handler.write_text("async def run(ctx):\n    return {'version': 1}\n", encoding="utf-8")
    node = config.nodes["rss-fetcher"].model_copy(update={"handler": "dynamic"})
    from edera_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("dynamic", handler)
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, registry.seal())

    first = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))
    handler.write_text("async def run(ctx):\n    return {'version': 2}\n", encoding="utf-8")
    second = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))

    assert first.payload == {"version": 1}
    assert second.payload == {"version": 1}


@pytest.mark.asyncio
async def test_node_executor_prefers_node_entity() -> None:
    config = _load_config()

    async def entity_handler(_node_input: NodeInput) -> dict[str, object]:
        return {"source": "entity"}

    async def legacy_handler(_node_input: NodeInput) -> dict[str, object]:
        return {"source": "legacy"}

    store = EntityStore(
        EntitiesConfig.model_validate(
            {
                "entities": [
                    {
                        "id": "entity-reader",
                        "type": "node",
                        "attributes": {
                            "name": "reader",
                            "type": "function",
                            "handler": "entity-handler",
                            "input_type": "RawItem",
                            "output_type": "AnalysisResult",
                        },
                    }
                ]
            }
        ),
        {"node": config.entity_types["node"]},
        EntityRelationsConfig(),
    )
    executor = NodeExecutor(
        {"reader": config.nodes["reader"].model_copy(update={"handler": "legacy-handler"})},
        config.system,
        config.runtime,
        handlers={"entity-handler": entity_handler, "legacy-handler": legacy_handler},
        entity_store=store,
    )

    output = await executor.execute("reader", NodeInput(run_id="run", payload={}))

    assert output.payload == {"source": "entity"}


@pytest.mark.asyncio
async def test_node_executor_reports_non_executable_entity() -> None:
    config = _load_config()
    store = EntityStore(
        EntitiesConfig.model_validate(
            {
                "entities": [
                    {
                        "id": "metadata-node",
                        "type": "node",
                        "attributes": {
                            "name": "metadata",
                            "type": "function",
                            "input_type": "JsonObject",
                            "output_type": "JsonObject",
                        },
                    }
                ]
            }
        ),
        {
            "node": EntityTypeConfig.model_validate(
                {
                    "display_name": "Node",
                    "business_id_field": "name",
                    "display_template": "{name}",
                    "schema": {
                        "required": ["name", "type", "input_type", "output_type"],
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "handler": {"type": "string"},
                            "system_prompt_file": {"type": "string"},
                            "input_type": {"type": "string"},
                            "output_type": {"type": "string"},
                        },
                    },
                }
            )
        },
        EntityRelationsConfig(),
    )
    executor = NodeExecutor({}, config.system, config.runtime, entity_store=store)

    output = await executor.execute("metadata", NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "handler not registered: metadata"


@pytest.mark.asyncio
async def test_system_zero_timeout_disables_wait_for() -> None:
    config = _load_config()

    async def handler(_node_input: NodeInput) -> dict[str, object]:
        return {"ok": True}

    node = config.nodes["rss-fetcher"].model_copy(update={"timeout_seconds": None})
    system = config.system.model_copy(update={"llm_timeout_seconds": 0})
    executor = NodeExecutor(
        {"rss-fetcher": node},
        system,
        config.runtime,
        handlers={"fetch-rss": handler},
    )

    output = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == {"ok": True}


@pytest.mark.asyncio
async def test_context_handler_receives_full_input_and_params(tmp_path: Path) -> None:
    config = _load_config()
    handler = tmp_path / "handler.py"
    handler.write_text(
        "async def run(ctx):\n"
        "    ctx.input.metadata['failures'] = {'source': 'failed'}\n"
        "    return {'payload': ctx.input.payload, 'limit': ctx.params['limit']}\n",
        encoding="utf-8",
    )
    node = config.nodes["rss-fetcher"].model_copy(update={"parameters": {"limit": 2}})
    from edera_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("fetch-rss", handler)
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, registry.seal())
    node_input = NodeInput(run_id="run", payload={"source_names": ["hn-rss"]}, metadata={})

    output = await executor.execute("rss-fetcher", node_input)

    assert output.payload == {"payload": {"source_names": ["hn-rss"]}, "limit": 2}
    assert "failures" not in output.metadata


@pytest.mark.asyncio
async def test_context_handler_records_source_recovery(tmp_path: Path) -> None:
    config = _load_config()
    handler = tmp_path / "handler.py"
    handler.write_text(
        "async def run(ctx):\n"
        "    await ctx.runtime.record_source_recovery('hn-rss', {'recovery_status': 'escalated'})\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    recorded: list[tuple[str, str, str, dict[str, object]]] = []

    async def recorder(run_id: str, node_id: str, source_name: str, summary: dict[str, object]) -> None:
        recorded.append((run_id, node_id, source_name, summary))

    from edera_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("fetch-rss", handler)
    executor = NodeExecutor(
        {"rss-fetcher": config.nodes["rss-fetcher"]},
        config.system,
        config.runtime,
        registry.seal(),
        source_recovery_recorder=recorder,
    )

    output = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert recorded == [("run", "rss-fetcher", "hn-rss", {"recovery_status": "escalated"})]


@pytest.mark.asyncio
async def test_pi_node_requires_instance_model() -> None:
    config = _load_config()
    node = NodeConfig(
        name="llm-node",
        type="function",
        handler="run-pi",
        input_type="Any",
        output_type="Any",
    )
    instance = DagNodeInstance(id="llm-1", type="llm-node", config={})
    executor = NodeExecutor(
        {"llm-node": node},
        config.system,
        config.runtime,
        handlers={"run-pi": _unused_handler},
        instances={instance.id: instance},
    )

    output = await executor.execute(instance.id, NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "model not configured for instance"


@pytest.mark.asyncio
async def test_instance_config_sets_model_tools_and_session_dir() -> None:
    config = _load_config()
    node = NodeConfig(
        name="llm-node",
        type="function",
        handler="run-pi",
        tools=["bash"],
        input_type="Any",
        output_type="Any",
    )
    instance = DagNodeInstance(
        id="llm-1",
        type="llm-node",
        config={
            "model": "hf-share/deepseek-v4-flash",
            "tools": ["bash", "read"],
            "session_dir": "sandbox:llm-0:latest",
        },
    )
    effective = _apply_instance_config(node, instance)

    assert effective.parameters["model"] == "hf-share/deepseek-v4-flash"
    assert effective.parameters["session_dir"] == "sandbox:llm-0:latest"
    assert effective.tools == ["bash", "read"]


@pytest.mark.asyncio
async def test_agent_executor_records_raw_log_file(tmp_path: Path) -> None:
    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\nprintf 'line one\\nline two\\n'\n", encoding="utf-8")
    pi.chmod(0o755)
    node = NodeConfig.model_validate(
        {
            "name": "agent-node",
            "type": "agent",
            "model": "test-model",
            "input_type": "Any",
            "output_type": "Any",
        }
    )
    runtime = RuntimeSettings(pi_bin=str(pi))
    records: list[tuple[str, str, str, str, int]] = []
    stdout: list[str] = []
    summaries: list[dict[str, object]] = []

    async def recorder(run_id: str, node_id: str, path: str, digest: str, size: int) -> None:
        records.append((run_id, node_id, path, digest, size))

    async def summary_recorder(_run_id: str, _node_id: str, summary: dict[str, object]) -> None:
        summaries.append(summary)

    executor = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        runtime,
        daemon_data_dir=tmp_path / "data",
        stdout_recorder=lambda _run, _node, line: _append(stdout, line),
        raw_log_recorder=recorder,
        execution_summary_recorder=summary_recorder,
    )

    output = await executor.execute("agent-node", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload["stdout"] == "line one\nline two"
    assert stdout == ["line one", "line two"]
    assert len(records) == 1
    run_id, node_id, log_path, digest, size = records[0]
    content = Path(log_path).read_bytes()
    assert run_id == "run-1"
    assert node_id == "agent-node"
    assert content == b"line one\nline two\n"
    assert digest == hashlib.sha256(content).hexdigest()
    assert size == len(content)
    assert summaries[0]["ok"] is True
    assert summaries[0]["session_id"] == output.metadata["session_id"]
    assert summaries[0]["raw_log_path"] == log_path


@pytest.mark.asyncio
async def test_agent_executor_records_failed_and_silent_summary(tmp_path: Path) -> None:
    failed_pi = tmp_path / "failed-pi"
    failed_pi.write_text("#!/bin/sh\nprintf 'partial\\n'\nexit 3\n", encoding="utf-8")
    failed_pi.chmod(0o755)
    silent_pi = tmp_path / "silent-pi"
    silent_pi.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    silent_pi.chmod(0o755)
    node = NodeConfig.model_validate(
        {
            "name": "agent-node",
            "type": "agent",
            "model": "test-model",
            "input_type": "Any",
            "output_type": "Any",
        }
    )
    records: list[tuple[str, str, str, str, int]] = []
    stdout: list[str] = []
    summaries: list[dict[str, object]] = []

    async def recorder(run_id: str, node_id: str, path: str, digest: str, size: int) -> None:
        records.append((run_id, node_id, path, digest, size))

    async def summary_recorder(_run_id: str, _node_id: str, summary: dict[str, object]) -> None:
        summaries.append(summary)

    failed = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(failed_pi)),
        daemon_data_dir=tmp_path / "failed-data",
        stdout_recorder=lambda _run, _node, line: _append(stdout, line),
        raw_log_recorder=recorder,
        execution_summary_recorder=summary_recorder,
    )
    silent = NodeExecutor(
        {"agent-node": node},
        SystemConfig(),
        RuntimeSettings(pi_bin=str(silent_pi)),
        daemon_data_dir=tmp_path / "silent-data",
        raw_log_recorder=recorder,
        execution_summary_recorder=summary_recorder,
    )

    failed_output = await failed.execute("agent-node", NodeInput(run_id="run-failed", payload={}))
    silent_output = await silent.execute("agent-node", NodeInput(run_id="run-silent", payload={}))

    assert not failed_output.ok
    assert "pi exited with code 3" == failed_output.error
    assert stdout == ["partial"]
    assert summaries[0]["ok"] is False
    assert summaries[0]["error"] == "pi exited with code 3"
    assert summaries[0]["raw_log_path"] == records[0][2]
    assert silent_output.ok
    assert silent_output.payload["stdout"] == ""
    assert summaries[1]["ok"] is True
    assert summaries[1]["raw_log_path"] == records[1][2]


@pytest.mark.asyncio
async def test_raw_log_index_is_queryable(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        await _record_raw_log(factory, "run-1", "agent-node", "/tmp/stdout.log", "digest", 12)

        async with factory() as session:
            rows = await query_log_index(session, run_id="run-1", node_id="agent-node")

        assert len(rows) == 1
        assert rows[0].path == "/tmp/stdout.log"
        assert rows[0].kind == "raw"
        assert rows[0].digest == "digest"
        assert rows[0].size == 12
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_log_index_is_queryable(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        summary = {
            "run_id": "run-1",
            "node_id": "node-1",
            "ok": True,
            "status": "succeeded",
            "error": None,
            "failure_kind": None,
            "payload_empty": False,
            "session_id": None,
            "raw_log_path": None,
        }
        path = tmp_path / "summary.json"
        await _record_summary_log(factory, "run-1", "node-1", path, summary)

        async with factory() as session:
            rows = await query_log_index(session, run_id="run-1", node_id="node-1")

        content = path.read_bytes()
        assert rows[0].kind == "summary"
        assert rows[0].path == str(path)
        assert rows[0].digest == hashlib.sha256(content).hexdigest()
        assert rows[0].size == len(content)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_log_index_kind_migrates_existing_table(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE TABLE log_index ("
                    "id INTEGER PRIMARY KEY, "
                    "run_id VARCHAR NOT NULL, "
                    "node_id VARCHAR NOT NULL, "
                    "path VARCHAR NOT NULL, "
                    "digest VARCHAR NOT NULL, "
                    "size INTEGER NOT NULL, "
                    "created_at DATETIME NOT NULL, "
                    "updated_at DATETIME NOT NULL)"
                )
            )
        await init_db(engine)

        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA table_info(log_index)"))

        assert "kind" in {row[1] for row in result.fetchall()}
    finally:
        await engine.dispose()


async def _unused_handler(_node_input: NodeInput) -> dict[str, object]:
    return {}


async def _append(items: list[str], value: str) -> None:
    items.append(value)
