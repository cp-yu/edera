from pathlib import Path
import tarfile

import pytest
import yaml

from edera_core.cli import main


def test_uninstall_no_strategy(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edera", "extension", "uninstall", "demo"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert "--strategy" in capsys.readouterr().err


def test_import_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "package"
    source.mkdir()
    (source / "manifest.yaml").write_text("name: demo\nversion: 0.1.0\n", encoding="utf-8")
    installed: list[str] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_install(self, name: str) -> dict[str, object]:
            installed.append(name)
            return {"installed": name}

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "--server",
            "127.0.0.1:0",
            "extension",
            "import",
            str(source),
            "--extensions-dir",
            str(tmp_path / "extensions"),
            "--install",
        ],
    )

    main()

    assert installed == ["demo"]
    assert (tmp_path / "extensions" / "demo" / "manifest.yaml").exists()
    assert '"installed": "demo"' in capsys.readouterr().out


def test_import_without_install_outputs_install_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "package"
    source.mkdir()
    (source / "manifest.yaml").write_text("name: demo\nversion: 0.1.0\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "extension",
            "import",
            str(source),
            "--extensions-dir",
            str(tmp_path / "extensions"),
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "edera extension install demo" in output


def test_list_without_flags_excludes_installed_from_available(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_list_available(self) -> dict[str, object]:
            return {"extensions": [{"name": "demo"}, {"name": "other"}]}

        async def extension_list_installed(self) -> dict[str, object]:
            return {"extensions": [{"name": "demo", "version": "0.1.0", "enabled": True}]}

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "--server", "127.0.0.1:0", "extension", "list"])

    main()

    output = capsys.readouterr().out
    assert '"installed": [{"name": "demo", "version": "0.1.0", "enabled": true}]' in output
    assert '"available": [{"name": "other"}]' in output


def test_export_includes_database_entities_and_handlers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "system.toml").write_text('handlers_dir = "data/handlers"\n', encoding="utf-8")
    handlers_dir = Path("data/handlers")
    package = tmp_path / "demo.tar.gz"
    handler_root = handlers_dir / "demo"
    handler_root.mkdir(parents=True)
    (handler_root / "handler.py").write_text("def run():\n    return None\n", encoding="utf-8")
    fetched: list[str] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_show(self, name: str) -> dict[str, object]:
            return {
                "manifest": {
                    "name": name,
                    "version": "0.1.0",
                    "imports": {"entities": ["entities/stock.yaml"]},
                    "handlers": ["handler.py"],
                },
                "import_records": [{"import_path": "entities/stock.yaml", "entity_ref": "stock:600000"}],
            }

        async def entity_get(self, ref: str) -> dict[str, object]:
            fetched.append(ref)
            return {"type": "stock", "id": "600000", "attributes": {"name": "浦发银行"}}

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "--server",
            "127.0.0.1:0",
            "extension",
            "export",
            "demo",
            "-o",
            str(package),
        ],
    )

    main()

    assert fetched == ["stock:600000"]
    assert '"warnings": []' in capsys.readouterr().out
    with tarfile.open(package, "r:gz") as archive:
        names = set(archive.getnames())
        assert "demo/manifest.yaml" in names
        assert "demo/entities/stock.yaml" in names
        assert "demo/handler.py" in names
        entity = archive.extractfile("demo/entities/stock.yaml")
        assert entity is not None
        assert "id: '600000'" in entity.read().decode("utf-8")


def test_export_warns_when_handlers_are_not_under_handlers_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "demo.tar.gz"

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_show(self, name: str) -> dict[str, object]:
            return {
                "manifest": {
                    "name": name,
                    "version": "0.1.0",
                    "handlers": [{"name": "external", "entry": "/tmp/external.py"}],
                },
                "import_records": [],
            }

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "--server",
            "127.0.0.1:0",
            "extension",
            "export",
            "demo",
            "-o",
            str(package),
            "--handlers-dir",
            str(tmp_path / "handlers"),
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "handler code not included" in output
    with tarfile.open(package, "r:gz") as archive:
        assert "demo/external.py" not in archive.getnames()


def test_export_workflow_extension_includes_providers_and_libraries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "workflow.tar.gz"
    handlers_dir = tmp_path / "handlers"
    libs_dir = handlers_dir / "_libs"
    (handlers_dir / "workflow.reader").mkdir(parents=True)
    (handlers_dir / "workflow.reader" / "handler.py").write_text("def run():\n    return None\n", encoding="utf-8")
    (libs_dir / "workflow.http_fetch").mkdir(parents=True)
    (libs_dir / "workflow.http_fetch" / "client.py").write_text("VALUE = 1\n", encoding="utf-8")

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_show(self, name: str) -> dict[str, object]:
            return {
                "manifest": {
                    "name": name,
                    "version": "0.1.0",
                    "type": "workflow_extension",
                    "imports": {
                        "providers": ["_providers/*/manifest.yaml"],
                        "libraries": ["_lib/http_fetch"],
                    },
                    "handlers": [
                        {
                            "name": "workflow.reader.read",
                            "package": "workflow.reader",
                            "entry": "handler.py",
                            "role": "processor",
                            "input_type": "Any",
                        }
                    ],
                },
                "import_records": [],
            }

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "--server",
            "127.0.0.1:0",
            "extension",
            "export",
            "workflow",
            "-o",
            str(package),
            "--handlers-dir",
            str(handlers_dir),
        ],
    )

    main()

    assert '"warnings": []' in capsys.readouterr().out
    with tarfile.open(package, "r:gz") as archive:
        names = set(archive.getnames())
        provider_manifest = archive.extractfile("workflow/_providers/reader/manifest.yaml")
        assert provider_manifest is not None
        assert yaml.safe_load(provider_manifest.read().decode("utf-8"))["handlers"][0]["name"] == "read"
        assert "workflow/_providers/reader/handler.py" in names
        assert "workflow/_lib/http_fetch/client.py" in names


def test_export_workflow_extension_warns_for_missing_provider_or_library(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "workflow.tar.gz"
    handlers_dir = tmp_path / "handlers"
    (handlers_dir / "workflow.reader").mkdir(parents=True)
    (handlers_dir / "workflow.reader" / "handler.py").write_text("def run():\n    return None\n", encoding="utf-8")

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_show(self, name: str) -> dict[str, object]:
            return {
                "manifest": {
                    "name": name,
                    "version": "0.1.0",
                    "type": "workflow_extension",
                    "imports": {
                        "providers": ["_providers/reader/manifest.yaml", "_providers/missing/manifest.yaml"],
                        "libraries": ["_lib/http_fetch"],
                    },
                    "handlers": [
                        {
                            "name": "workflow.reader.read",
                            "package": "workflow.reader",
                            "entry": "handler.py",
                            "role": "processor",
                            "input_type": "Any",
                        },
                        {
                            "name": "workflow.missing.read",
                            "package": "workflow.missing",
                            "entry": "handler.py",
                            "role": "processor",
                            "input_type": "Any",
                        },
                    ],
                },
                "import_records": [],
            }

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "--server",
            "127.0.0.1:0",
            "extension",
            "export",
            "workflow",
            "-o",
            str(package),
            "--handlers-dir",
            str(handlers_dir),
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "provider code not included" in output
    assert "library code not included" in output
    with tarfile.open(package, "r:gz") as archive:
        names = set(archive.getnames())
        assert "workflow/_providers/reader/handler.py" in names


def test_install_overwrite_passes_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_install(self, name: str, overwrite: bool = False) -> dict[str, object]:
            calls.append({"name": name, "overwrite": overwrite})
            return {"overwrite": overwrite, "data_warning": "warn"}

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "--server", "127.0.0.1:0", "extension", "install", "demo", "--overwrite"],
    )

    main()

    assert calls == [{"name": "demo", "overwrite": True}]
    assert '"overwrite": true' in capsys.readouterr().out


def test_import_overwrite_replaces_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "package"
    source.mkdir()
    (source / "manifest.yaml").write_text("name: demo\nversion: 0.1.0\n", encoding="utf-8")
    (source / "old.txt").write_text("from-source", encoding="utf-8")
    extensions_dir = tmp_path / "extensions"
    target = extensions_dir / "demo"
    target.mkdir(parents=True)
    (target / "stale.txt").write_text("stale", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "extension",
            "import",
            str(source),
            "--extensions-dir",
            str(extensions_dir),
            "--overwrite",
        ],
    )

    main()

    assert (target / "old.txt").read_text(encoding="utf-8") == "from-source"
    assert not (target / "stale.txt").exists()


def test_import_without_overwrite_rejects_existing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "package"
    source.mkdir()
    (source / "manifest.yaml").write_text("name: demo\nversion: 0.1.0\n", encoding="utf-8")
    extensions_dir = tmp_path / "extensions"
    (extensions_dir / "demo").mkdir(parents=True)

    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "extension",
            "import",
            str(source),
            "--extensions-dir",
            str(extensions_dir),
        ],
    )

    with pytest.raises(SystemExit):
        main()


def test_delete_command_invokes_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    deleted: list[str] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_delete(self, name: str) -> dict[str, object]:
            deleted.append(name)
            return {"deleted": True, "name": name}

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "--server", "127.0.0.1:0", "extension", "delete", "demo"])

    main()

    assert deleted == ["demo"]
    assert '"deleted": true' in capsys.readouterr().out


def test_import_entities_command_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "backup.tar.gz"
    package.write_bytes(b"tar")
    uploaded: list[str] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def extension_import_entities(self, path: str) -> dict[str, object]:
            uploaded.append(path)
            return {"imported": 0, "updated": 2}

        async def close(self) -> None:
            pass

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "--server", "127.0.0.1:0", "extension", "import-entities", "-f", str(package)],
    )

    main()

    assert uploaded == [str(package)]
    assert '"updated": 2' in capsys.readouterr().out
