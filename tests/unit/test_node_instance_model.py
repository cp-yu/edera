from stockimformation.config.schema import DagNodeInstance


def test_entities_field() -> None:
    instance = DagNodeInstance(
        id="node-1",
        type="rss-fetcher",
        config={"entities": ["stock:00700.HK"], "entity_permissions": {"stock": {"code": "read-write"}}},
    )
    assert instance.config["entities"] == ["stock:00700.HK"]
