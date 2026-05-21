import pytest
import yaml
from sqlmodel import select

from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from stockimformation.errors import ConfigError
from stockimformation.models.database import create_engine, init_db, session_factory, sqlite_url
from stockimformation.models.entities import NodeOutputEntity
from stockimformation.node.models import NodeContext


def _context() -> NodeContext:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {"display_name": "Stock", "business_id_field": "code", "display_template": "{code}"}
        )
    }
    entities = EntitiesConfig.model_validate(
        {"entities": [{"id": "stock-1", "type": "stock", "attributes": {"code": "00700.HK"}}]}
    )
    return NodeContext("cycle", "node", entity_store=EntityStore(entities, entity_types, EntityRelationsConfig()))


def test_get_entity() -> None:
    assert _context().get_entity("stock:00700.HK") is not None


def test_save_entity() -> None:
    context = _context()
    entity = context.get_entity("stock-1")
    assert entity is not None
    entity.attributes["name"] = "Tencent"
    saved = context.save_entity(entity)
    assert saved is not None
    assert saved.attributes["name"] == "Tencent"


def test_create_entity() -> None:
    entity = _context().create_entity("stock", {"code": "600519.SH"})
    assert entity is not None
    assert entity.type == "stock"


def test_create_entity_validates_attributes() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "schema": {"required": ["code", "name"]},
            }
        )
    }
    context = NodeContext("cycle", "node", entity_store=EntityStore(EntitiesConfig(), entity_types, EntityRelationsConfig()))
    with pytest.raises(ConfigError):
        context.create_entity("stock", {"code": "600519.SH"})


def test_save_entity_persists_config(tmp_path) -> None:
    config_dir = tmp_path / "config"
    schema_dir = tmp_path / "schemas" / "entity-types"
    config_dir.mkdir()
    schema_dir.mkdir(parents=True)
    schema_dir.joinpath("stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "schema:\n"
        "  required: [code]\n"
        "field_permissions:\n"
        "  code: read-only\n",
        encoding="utf-8",
    )
    path = config_dir / "entities.yaml"
    path.write_text("entities:\n- id: stock-1\n  type: stock\n  attributes:\n    code: 00700.HK\n", encoding="utf-8")
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "schema": {"required": ["code"]},
                "field_permissions": {"code": "read-only"},
            }
        )
    }
    entities = EntitiesConfig.model_validate(
        {"entities": [{"id": "stock-1", "type": "stock", "attributes": {"code": "00700.HK"}}]}
    )
    context = NodeContext(
        "cycle",
        "node",
        entity_store=EntityStore(entities, entity_types, EntityRelationsConfig(), path),
    )
    entity = context.get_entity("stock-1")
    assert entity is not None
    entity.attributes["name"] = "Tencent"
    context.save_entity(entity)
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert saved["entities"][0]["attributes"]["name"] == "Tencent"


def test_entity_store_three_tiers(tmp_path) -> None:
    config_dir = tmp_path / "config"
    schema_dir = tmp_path / "schemas" / "entity-types"
    config_dir.mkdir()
    schema_dir.mkdir(parents=True)
    path = config_dir / "entities.yaml"
    path.write_text("entities: []\n", encoding="utf-8")
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "storage_tier": "filesystem",
                "schema": {"required": ["code"], "properties": {"code": {"type": "string"}}},
            }
        ),
        "analysis": EntityTypeConfig.model_validate(
            {
                "display_name": "Analysis",
                "business_id_field": "id",
                "display_template": "{id}",
                "storage_tier": "database",
                "schema": {"required": ["id"], "properties": {"id": {"type": "string"}}},
            }
        ),
        "run-metadata": EntityTypeConfig.model_validate(
            {
                "display_name": "Run",
                "business_id_field": "cycle_id",
                "display_template": "{cycle_id}",
                "storage_tier": "memory",
                "schema": {"required": ["cycle_id"], "properties": {"cycle_id": {"type": "string"}}},
            }
        ),
    }
    for name, entity_type in entity_types.items():
        schema_dir.joinpath(f"{name}.yaml").write_text(
            yaml.safe_dump(entity_type.model_dump(by_alias=True), sort_keys=False),
            encoding="utf-8",
        )
    store = EntityStore(EntitiesConfig(), entity_types, EntityRelationsConfig(), path)

    store.create("stock", {"code": "00700.HK"})
    analysis = store.create("analysis", {"id": "analysis-1", "cycle_id": "cycle-1", "node_id": "reader", "tags": ["stock:00700.HK"]})
    run = store.create("run-metadata", {"cycle_id": "cycle-1"})

    assert (config_dir / "entities" / "00700.HK.yaml").exists()
    assert store.resolve(f"analysis:{analysis.attributes['id']}").id == analysis.id
    assert store.query("analysis", cycle_id="cycle-1", node_id="reader", tags=["stock:00700.HK"])[0].id == analysis.id
    assert store.resolve(f"run-metadata:{run.attributes['cycle_id']}").id == run.id
    store.release_run("cycle-1")
    assert store.query("run-metadata") == []


@pytest.mark.asyncio
async def test_entity_store_three_tiers_uses_database_layer(tmp_path) -> None:
    entity_types = {
        "analysis": EntityTypeConfig.model_validate(
            {
                "display_name": "Analysis",
                "business_id_field": "id",
                "display_template": "{id}",
                "storage_tier": "database",
                "schema": {"required": ["id"], "properties": {"id": {"type": "string"}}},
            }
        )
    }
    store = EntityStore(EntitiesConfig(), entity_types, EntityRelationsConfig())
    engine = create_engine(sqlite_url(tmp_path / "entities.db"))
    await init_db(engine)
    factory = session_factory(engine)

    async with factory() as session:
        created = await store.create_async(
            "analysis",
            {
                "id": "analysis-1",
                "cycle_id": "cycle-1",
                "node_id": "reader",
                "payload": {"summary": "ok", "tags": ["stock:00700.HK"]},
            },
            session,
        )
        await session.commit()
        result = await session.exec(select(NodeOutputEntity))
        queried = await store.query_async("analysis", cycle_id="cycle-1", session=session)

    assert len(result.all()) == 1
    assert queried[0].id == created.id
    assert queried[0].attributes["payload"]["summary"] == "ok"
