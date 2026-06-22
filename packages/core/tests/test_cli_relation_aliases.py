from __future__ import annotations

import argparse

import pytest

from edera_core import cli
from edera_core.cli import entity as cli_entity


@pytest.mark.asyncio
async def test_relation_list_alias(monkeypatch):
    captured = {}

    async def fake_entity(args):
        captured.update(vars(args))
        return []

    monkeypatch.setattr(cli, "_grpc_entity", fake_entity)
    args = argparse.Namespace(
        relation_command="list",
        from_="stock:test",
        to="rss:test",
        type="uses-source",
        server=None,
        identity="human",
    )

    await cli._grpc_relation(args)

    assert captured["type"] == "relation"
    assert captured["filter"] == ["from_entity_id=stock:test", "to_entity_id=rss:test", "relation_type=uses-source"]


@pytest.mark.asyncio
async def test_relation_create_alias(monkeypatch):
    captured = {}

    async def fake_entity(args):
        captured.update(vars(args))
        return {}

    monkeypatch.setattr(cli, "_grpc_entity", fake_entity)
    args = argparse.Namespace(
        relation_command="create",
        from_="stock:test",
        to="rss-source:test",
        type="uses-source",
        metadata="{}",
        server=None,
        identity="human",
    )

    await cli._grpc_relation(args)

    assert captured["type"] == "relation"
    assert captured["attributes"] == '{"from_entity_id":"stock:test","to_entity_id":"rss-source:test","relation_type":"uses-source","metadata":{}}'


@pytest.mark.asyncio
async def test_relation_import_alias(monkeypatch, tmp_path):
    captured = {}

    async def fake_entity(args):
        captured.update(vars(args))
        return {}

    monkeypatch.setattr(cli, "_grpc_entity", fake_entity)
    path = tmp_path / "relations.yaml"
    args = argparse.Namespace(relation_command="import", file=path, server=None, identity="human")

    await cli._grpc_relation(args)

    assert captured["entity_command"] == "import"
    assert captured["type"] == "relation"
