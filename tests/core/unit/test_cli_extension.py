from pathlib import Path
import tarfile

import pytest

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
