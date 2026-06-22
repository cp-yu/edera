from __future__ import annotations

import argparse

import pytest

from edera_core import cli
from edera_core.cli import skill as cli_skill


@pytest.mark.asyncio
async def test_skill_list(monkeypatch):
    client = _Client()
    monkeypatch.setattr("edera_core.cli.GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(server=None, identity="human", skill_command="list")

    result = await cli_skill._grpc_skill(args)

    assert result["skills"][0]["name"] == "demo"
    assert result["skills"][0]["display_name"] == "Demo"
    assert result["skills"][0]["description"] == "skill"


@pytest.mark.asyncio
async def test_skill_import_dir(monkeypatch, tmp_path):
    client = _Client()
    monkeypatch.setattr("edera_core.cli.GrpcClient", lambda *args, **kwargs: client)
    source = tmp_path / "demo"
    source.mkdir()
    (source / "SKILL.md").write_text("# Demo", encoding="utf-8")
    args = argparse.Namespace(server=None, identity="human", skill_command="import-dir", path=source)

    result = await cli_skill._grpc_skill(args)

    assert result["skill"]["name"] == "demo"
    assert client.saved_name == "demo"
    assert client.payload["files"] == [{"path": "SKILL.md", "content": "# Demo"}]


@pytest.mark.asyncio
async def test_skill_import_batch(monkeypatch, tmp_path):
    client = _Client()
    monkeypatch.setattr("edera_core.cli.GrpcClient", lambda *args, **kwargs: client)
    source = tmp_path / "skills"
    for name in ("a", "b"):
        root = source / name
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(name, encoding="utf-8")
    args = argparse.Namespace(server=None, identity="human", skill_command="import-batch", path=source)

    result = await cli_skill._grpc_skill(args)

    assert result["imported"] == ["a", "b"]
    assert client.saved_names == ["a", "b"]


@pytest.mark.asyncio
async def test_skill_import_dir_updates_existing(monkeypatch, tmp_path):
    client = _Client()
    monkeypatch.setattr("edera_core.cli.GrpcClient", lambda *args, **kwargs: client)
    source = tmp_path / "demo"
    source.mkdir()
    skill_md = source / "SKILL.md"
    args = argparse.Namespace(server=None, identity="human", skill_command="import-dir", path=source)

    skill_md.write_text("old", encoding="utf-8")
    await cli_skill._grpc_skill(args)
    skill_md.write_text("new", encoding="utf-8")
    await cli_skill._grpc_skill(args)

    assert client.saved_names == ["demo", "demo"]
    assert client.saved_payloads[-1]["files"] == [{"path": "SKILL.md", "content": "new"}]


@pytest.mark.asyncio
async def test_skill_export_preserves_files(monkeypatch, tmp_path):
    client = _Client()
    monkeypatch.setattr("edera_core.cli.GrpcClient", lambda *args, **kwargs: client)
    args = argparse.Namespace(server=None, identity="human", skill_command="export", name="demo", output_dir=tmp_path / "out")

    result = await cli_skill._grpc_skill(args)

    assert result["exported"] == "demo"
    assert (tmp_path / "out" / "demo" / "SKILL.md").read_text(encoding="utf-8") == "# Demo"
    assert (tmp_path / "out" / "demo" / "prompts" / "main.txt").read_text(encoding="utf-8") == "prompt"


class _Client:
    def __init__(self):
        self.payload = None
        self.saved_name = None
        self.saved_names = []
        self.saved_payloads = []

    async def close(self) -> None:
        return None

    async def graph_list_skills(self):
        return {
            "skills": [
                {
                    "name": "demo",
                    "display_name": "Demo",
                    "description": "skill",
                    "files": [
                        {"path": "SKILL.md", "content": "# Demo"},
                        {"path": "prompts/main.txt", "content": "prompt"},
                    ],
                }
            ]
        }

    async def graph_create_skill(self, payload):
        self.payload = payload
        return {"skill": {"name": payload["name"]}}

    async def graph_save_skill(self, name, payload):
        self.saved_name = name
        self.saved_names.append(name)
        self.saved_payloads.append(payload)
        self.payload = payload
        return {"skill": {"name": name}}
