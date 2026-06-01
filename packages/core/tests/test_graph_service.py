from __future__ import annotations

import json

import grpc
import pytest

from edera_core.graph_service import _GraphService
from edera_core.proto import edera_pb2 as pb2
from edera_core.registry import HandlerRegistry

from service_fakes import AbortError, FakeContext, FakeDaemon


@pytest.mark.asyncio
async def test_save_invalid_dag(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(FakeDaemon(root))

    with pytest.raises(AbortError) as exc:
        await service.SaveDag(
            pb2.NamedJsonRequest(
                name="demo",
                json=json.dumps({"nodes": [{"id": "n1", "type": "missing"}], "edges": []}),
            ),
            FakeContext(),
        )

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_delete_referenced_node_type(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(FakeDaemon(root))

    with pytest.raises(AbortError) as exc:
        await service.DeleteNodeType(pb2.NameRequest(name="reader"), FakeContext())

    assert exc.value.code == grpc.StatusCode.FAILED_PRECONDITION


@pytest.mark.asyncio
async def test_create_skill(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(FakeDaemon(root))

    result = await service.CreateSkill(
        pb2.JsonRequest(json=json.dumps({"name": "summarize", "description": "x", "handler_code": "def handle(): pass"})),
        FakeContext(),
    )

    assert json.loads(result.json)["skill"]["name"] == "summarize"
    assert (root / "skills" / "summarize.yaml").exists()
    assert (root.parent / "extensions" / "summarize" / "handler.py").exists()


@pytest.mark.asyncio
async def test_get_dag_detail(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(FakeDaemon(root))

    result = await service.GetDag(pb2.NameRequest(name="demo"), FakeContext())
    payload = json.loads(result.json)

    assert {"nodes", "edges", "ui", "entity_types", "entities", "entity_relations"}.issubset(payload)


@pytest.mark.asyncio
async def test_optional_save_response(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(FakeDaemon(root))

    result = await service.SaveDag(
        pb2.NamedJsonRequest(
            name="demo",
            json=json.dumps(
                {
                    "nodes": [{"id": "n1", "type": "reader", "optional": True}, {"id": "n2", "type": "reader"}],
                    "edges": [{"from": "n1", "to": "n2", "optional": True, "fan_in": True, "fan_in_mode": "collect"}],
                    "ui": {},
                }
            ),
        ),
        FakeContext(),
    )
    payload = json.loads(result.json)["dag"]

    assert payload["nodes"][0]["optional"] is True
    assert payload["edges"][0]["optional"] is True
    assert payload["edges"][0]["fan_in"] is True
    assert payload["edges"][0]["fan_in_mode"] == "collect"


@pytest.mark.asyncio
async def test_optional_round_trip(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(FakeDaemon(root))

    first = await service.SaveDag(
        pb2.NamedJsonRequest(
            name="demo",
            json=json.dumps(
                {
                    "nodes": [{"id": "n1", "type": "reader", "optional": True}, {"id": "n2", "type": "reader"}],
                    "edges": [{"from": "n1", "to": "n2", "optional": True}],
                    "ui": {},
                }
            ),
        ),
        FakeContext(),
    )
    saved = json.loads(first.json)["dag"]
    second = await service.SaveDag(pb2.NamedJsonRequest(name="demo", json=json.dumps(saved)), FakeContext())
    payload = json.loads(second.json)["dag"]

    assert payload["nodes"][0]["optional"] is True
    assert payload["edges"][0]["optional"] is True
    assert "optional: true" in (root / "dags" / "demo.yaml").read_text(encoding="utf-8")


# --- Handler registry tests ---


def _daemon_with_handlers(tmp_path, handler_files: dict[str, str]):
    root = tmp_path / "config"
    _write_graph_config(root)
    registry = HandlerRegistry()
    for name, content in handler_files.items():
        path = tmp_path / "handlers" / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        registry.register(name, path)
    return _FakeDaemonWithHandlers(root, registry.seal())


class _FakeDaemonWithHandlers:
    def __init__(self, config_dir, handler_registry):
        self.config_dir = config_dir
        self.pb2 = pb2
        self.controller = _FakeSnapshot(handler_registry)


class _FakeSnapshot:
    def __init__(self, handler_registry):
        self.bootstrap = _FakeBootstrap(handler_registry)

    def runtime_snapshot(self):
        return self


class _FakeBootstrap:
    def __init__(self, handler_registry):
        self.handler_registry = handler_registry


@pytest.mark.asyncio
async def test_list_handlers_returns_registry_entries(tmp_path):
    daemon = _daemon_with_handlers(tmp_path, {"reader": "def run(): pass", "fetcher": "def run(): pass"})
    service = _GraphService(daemon)
    result = await service.ListHandlers(pb2.EmptyRequest(), FakeContext())
    payload = json.loads(result.json)
    names = [h["name"] for h in payload["handlers"]]
    assert "reader" in names
    assert "fetcher" in names


@pytest.mark.asyncio
async def test_get_handler_reads_from_registry_path(tmp_path):
    daemon = _daemon_with_handlers(tmp_path, {"reader": "async def run(ctx): return []\n"})
    service = _GraphService(daemon)
    result = await service.GetHandler(pb2.NameRequest(name="reader"), FakeContext())
    payload = json.loads(result.json)
    assert payload["name"] == "reader"
    assert payload["code"] == "async def run(ctx): return []\n"


@pytest.mark.asyncio
async def test_get_handler_not_found_not_in_registry(tmp_path):
    daemon = _daemon_with_handlers(tmp_path, {"reader": "def run(): pass"})
    service = _GraphService(daemon)
    with pytest.raises(AbortError) as exc:
        await service.GetHandler(pb2.NameRequest(name="nonexistent"), FakeContext())
    assert exc.value.code == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_save_handler_writes_to_registry_path(tmp_path):
    daemon = _daemon_with_handlers(tmp_path, {"reader": "def run(): pass"})
    service = _GraphService(daemon)
    result = await service.SaveHandler(
        pb2.NamedTextRequest(name="reader", content="def run(): updated"),
        FakeContext(),
    )
    payload = json.loads(result.json)
    assert payload["code"] == "def run(): updated"
    handler_path = tmp_path / "handlers" / "reader.py"
    assert handler_path.read_text(encoding="utf-8") == "def run(): updated"


def _write_graph_config(root):
    (root / "dags").mkdir(parents=True)
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema:\n  properties:\n    code: {}\n",
        encoding="utf-8",
    )
    (root / "nodes" / "reader.yaml").write_text(
        "name: reader\ntype: function\nrole: processor\nhandler: reader\ninput_type: Any\noutput_type: Any\n",
        encoding="utf-8",
    )
    (root / "dags" / "demo.yaml").write_text(
        "name: demo\nnodes:\n- id: n1\n  type: reader\n- id: n2\n  type: reader\nedges: []\nui: {}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
