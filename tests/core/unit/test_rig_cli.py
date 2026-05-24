import pytest

from stockimformation_core.storage import create_engine, init_db, session_factory
from stockimformation_core.storage.repository import store_node_output_entities
from stockimformation_core.rig_cli import main


def test_rig_entity_update_denies_node_without_permission(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--identity",
            "node:reader",
            "entity",
            "update",
            "stock:00700.HK",
            "--field",
            "code",
            "--value",
            "001",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "Permission denied: node:reader cannot write stock.code" in capsys.readouterr().err


def test_rig_entity_query_lists_matching_entities(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["rig", "entity", "query", "type=stock"])

    main()

    assert "stock:00700.HK" in capsys.readouterr().out


def test_rig_entity_update_human_writes_field(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    schema_dir = tmp_path / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True)
    (schema_dir / "stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [code, name]\n"
        "  properties:\n"
        "    code:\n"
        "      type: string\n"
        "    name:\n"
        "      type: string\n"
        "field_permissions:\n"
        "  code: read-only\n",
        encoding="utf-8",
    )
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, type, input_type, output_type]\n"
        "  properties:\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "dag.yaml").write_text(
        "display_name: DAG\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, nodes, edges]\n"
        "  properties:\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text(
        "entities:\n"
        "- id: stock-test\n"
        "  type: stock\n"
        "  attributes:\n"
        "    code: TEST\n"
        "    name: Test\n",
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        'database_url = "sqlite+aiosqlite:///data/test.db"\nweb_host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir()
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    (config_dir / "nodes").mkdir()
    (config_dir / "nodes" / "node-a.yaml").write_text(
        "name: node-a\n"
        "type: function\n"
        "handler: node-a\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (config_dir / "skills").mkdir()
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--config-dir",
            str(config_dir),
            "entity",
            "update",
            "stock:TEST",
            "--field",
            "sentiment",
            "--value",
            "bearish",
        ],
    )

    main()

    assert '"sentiment": "bearish"' in capsys.readouterr().out


def test_rig_node_status_uses_http_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["rig", "node", "status", "reader"])
    monkeypatch.setattr("stockimformation_core.rig_cli._post", lambda api_url, path, payload, method="POST": {"node_id": "reader", "status": "idle"})

    main()

    assert '"status": "idle"' in capsys.readouterr().out


def test_rig_dag_trigger_sends_payload(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, object, str]] = []

    def fake_post(api_url: str, path: str, payload: object, method: str = "POST") -> object:
        calls.append((path, payload, method))
        return {"cycle_id": "cycle-1"}

    monkeypatch.setattr("sys.argv", ["rig", "dag", "trigger", "default", "--payload", '{"x": 1}'])
    monkeypatch.setattr("stockimformation_core.rig_cli._post", fake_post)

    main()

    assert calls == [("/api/pipeline/dag/default/run", {"payload": {"x": 1}}, "POST")]
    assert '"cycle_id": "cycle-1"' in capsys.readouterr().out


def test_rig_node_resume_sends_prompt(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, object, str]] = []

    def fake_post(api_url: str, path: str, payload: object, method: str = "POST") -> object:
        calls.append((path, payload, method))
        return {"cycle_id": "cycle-2"}

    monkeypatch.setattr("sys.argv", ["rig", "node", "resume", "reader", "--prompt", "adjust"])
    monkeypatch.setattr("stockimformation_core.rig_cli._post", fake_post)

    main()

    assert calls == [("/api/node/reader/resume", {"prompt": "adjust"}, "POST")]
    assert '"cycle_id": "cycle-2"' in capsys.readouterr().out


def test_rig_get_filters_unreadable_fields(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    monkeypatch.setattr("sys.argv", ["rig", "--config-dir", str(config_dir), "--identity", "node:reader", "entity", "get", "stock:TEST"])

    main()

    output = capsys.readouterr().out
    assert '"name": "Test"' in output
    assert '"secret":' not in output


def test_rig_query_supports_relations(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "entity-relations.yaml").write_text(
        "relations:\n"
        "- id: rel-1\n"
        "  entities: [stock:TEST, stock:TEST]\n"
        "  type: reflects\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["rig", "--config-dir", str(config_dir), "entity", "query", "relation_type=reflects AND to=stock:TEST"],
    )

    main()

    assert '"relation_type": "reflects"' in capsys.readouterr().out


def test_rig_query_supports_node_output_history(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    import asyncio

    async def seed() -> None:
        await init_db(engine)
        try:
            factory = session_factory(engine)
            async with factory() as session:
                await store_node_output_entities(session, "cycle-1", "reader", "analysis", {"summary": "done"}, "session-1")
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    monkeypatch.setattr("sys.argv", ["rig", "--config-dir", str(config_dir), "entity", "query", "node_id=reader"])

    main()

    assert '"summary": "done"' in capsys.readouterr().out


def _minimal_config(tmp_path) -> object:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    schema_dir = tmp_path / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True)
    (schema_dir / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema:\n  type: object\n  required: [code, name]\n  properties:\n    code:\n      type: string\n    name:\n      type: string\n    secret:\n      type: string\nfield_permissions:\n  code: read-only\n  secret: none\n",
        encoding="utf-8",
    )
    (schema_dir / "relation.yaml").write_text(
        "display_name: Relation\nbusiness_id_field: relation_type\ndisplay_template: '{from} -> {to}'\nschema:\n  type: object\n  required: [from, to, relation_type]\n  properties:\n    from:\n      type: string\n    to:\n      type: string\n    relation_type:\n      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  type: object\n  required: [name, type, input_type, output_type]\n  properties:\n    name:\n      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "dag.yaml").write_text(
        "display_name: DAG\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  type: object\n  required: [name, nodes, edges]\n  properties:\n    name:\n      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text(
        "entities:\n- id: stock-test\n  type: stock\n  attributes:\n    code: TEST\n    name: Test\n    secret: hidden\n",
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{tmp_path / "test.db"}"\nweb_host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir()
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    (config_dir / "nodes").mkdir()
    (config_dir / "skills").mkdir()
    return config_dir
