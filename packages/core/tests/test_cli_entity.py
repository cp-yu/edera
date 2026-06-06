from __future__ import annotations

import argparse

import pytest

from edera_core import cli


@pytest.mark.asyncio
async def test_entity_list_filters(monkeypatch):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(
        server=None,
        identity="human",
        entity_command="list",
        type="relation",
        filter=["from_entity_id=stock:test"],
    )

    result = await cli._grpc_entity(args)

    assert [item["id"] for item in result] == ["r1"]
    assert client.filters == {"from_entity_id": "stock:test"}


@pytest.mark.asyncio
async def test_entity_list_multiple_filters(monkeypatch):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(
        server=None,
        identity="human",
        entity_command="list",
        type="relation",
        filter=["from_entity_id=stock:test", "relation_type=uses-source"],
    )

    result = await cli._grpc_entity(args)

    assert [item["id"] for item in result] == ["r1"]
    assert client.filters == {"from_entity_id": "stock:test", "relation_type": "uses-source"}


@pytest.mark.asyncio
async def test_entity_create(monkeypatch):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(
        server=None,
        identity="human",
        entity_command="create",
        type="stock",
        id="test-stock",
        attributes='{"code":"TEST","name":"Test"}',
    )

    result = await cli._grpc_entity(args)

    assert result["id"] == "test-stock"
    assert result["attributes"]["code"] == "TEST"


@pytest.mark.asyncio
async def test_entity_create_requires_attributes(monkeypatch):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(
        server=None,
        identity="human",
        entity_command="create",
        type="stock",
        id="test-stock",
        attributes=None,
    )

    with pytest.raises(ValueError, match="Missing required parameter: --attributes"):
        await cli._grpc_entity(args)


@pytest.mark.asyncio
async def test_entity_show_alias(monkeypatch):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(server=None, identity="human", entity_command="show", ref="stock:test")

    result = await cli._grpc_entity(args)

    assert result["id"] == "stock:test"


@pytest.mark.asyncio
async def test_entity_update_attributes(monkeypatch):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(
        server=None,
        identity="human",
        entity_command="update",
        ref="stock:test",
        field=None,
        value=None,
        attributes='{"name":"New"}',
    )

    result = await cli._grpc_entity(args)

    assert result["attributes"]["name"] == "New"


@pytest.mark.asyncio
async def test_entity_import(monkeypatch, tmp_path):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    path = tmp_path / "entities.yaml"
    path.write_text("entities:\n- id: stock:test\n  type: stock\n  attributes:\n    code: TEST\n", encoding="utf-8")
    args = argparse.Namespace(server=None, identity="human", entity_command="import", file=path)

    result = await cli._grpc_entity(args)

    assert result == {"imported": 1}


@pytest.mark.asyncio
async def test_entity_export(monkeypatch, tmp_path):
    client = _Client()
    monkeypatch.setattr(cli, "GrpcClient", lambda *args, **kwargs: client)
    path = tmp_path / "entities.yaml"
    args = argparse.Namespace(server=None, identity="human", entity_command="export", ref=None, file=path, type=None)

    result = await cli._grpc_entity(args)

    assert result["exported"] == 3
    assert "entities:" in path.read_text(encoding="utf-8")


class _Client:
    def __init__(self):
        self.filters = None

    async def close(self):
        pass

    async def entity_list(self, type_name=None, filters=None, dag_run_id=None):
        self.filters = filters
        entities = [
            {"id": "r1", "type": "relation", "attributes": {"from_entity_id": "stock:test", "relation_type": "uses-source"}},
            {"id": "r2", "type": "relation", "attributes": {"from_entity_id": "stock:other", "relation_type": "uses-source"}},
            {"id": "s1", "type": "stock", "attributes": {"code": "TEST"}},
        ]
        return [
            entity
            for entity in entities
            if type_name is None or entity["type"] == type_name
            if all(entity["attributes"].get(key) == value for key, value in (filters or {}).items())
        ]

    async def entity_create(self, type_name, attributes, entity_id=""):
        return {"id": entity_id or "generated", "type": type_name, "attributes": attributes}

    async def entity_get(self, ref):
        return {"id": ref, "type": "stock", "attributes": {"code": "TEST"}}

    async def entity_update(self, ref, field, value):
        return {"id": ref, "type": "stock", "attributes": {field: value}}

    async def entity_import(self, path, type_name=None):
        return {"imported": 1}

    async def entity_export(self, type_name=None):
        return {"exported": 3, "content": "entities: []\n"}
