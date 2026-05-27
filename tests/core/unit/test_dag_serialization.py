from edera_core.config.schema import DagConfig


def test_serialize_with_entities() -> None:
    dag = DagConfig.model_validate(
        {
            "name": "default",
            "nodes": [
                {
                    "id": "node-1",
                    "type": "rss-fetcher",
                    "config": {"entities": ["stock:00700.HK"], "entity_permissions": {"stock": {"code": "read-write"}}},
                }
            ],
            "edges": [],
        }
    )
    payload = dag.model_dump(mode="json")
    assert payload["nodes"][0]["config"]["entities"] == ["stock:00700.HK"]
