from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import grpc
import yaml

from edera_core.cli._common import (
    _entity_document,
    _write_entity_yaml,
)
from edera_core.config.loader import load_system_config
import edera_core.cli as _cli
from edera_core.handler_validator import validate_handler
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage installed extensions (扩展).",
    help_line="Manage extensions (扩展)",
    epilog=_fmt_epilog(
        "Extensions package handlers, entity-types and skills; install/uninstall drive lifecycle.",
        [
            ("edera extension list --installed", "list installed extensions"),
            ("edera extension install my-ext", "install an extension"),
            ("edera extension uninstall my-ext --strategy purge", "fully remove an extension"),
            ("edera extension import ./my-ext --install", "import and install from a path"),
        ],
    ),
    subcommands={
        "list": "List available or installed extensions.",
        "show": "Show a single extension by name.",
        "install": "Install an extension by name.",
        "delete": "Delete an installed extension (alias of uninstall --strategy deactivate).",
        "uninstall": "Uninstall with a strategy (purge | keep-modified | deactivate).",
        "reactivate": "Reactivate a previously deactivated extension.",
        "import": "Import an extension from a path (optionally --install).",
        "export": "Export an extension to an archive.",
        "import-entities": "Import entities bundled in an extension.",
        "export-entities": "Export entities into an extension archive.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="extension_command", required=True)
    sub = HELP.subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    list_.add_argument("--available", action="store_true", help="List available extensions only.")
    list_.add_argument("--installed", action="store_true", help="List installed extensions only.")
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name", help="Extension name.")
    show.add_argument("--extensions-dir", type=Path, default=Path("extensions"), help="Extensions directory path.")
    install = subparsers.add_parser("install", help=sub["install"])
    install.add_argument("name", help="Extension name.")
    install.add_argument("--overwrite", action="store_true", help="Overwrite if already installed.")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("name", help="Extension name.")
    uninstall = subparsers.add_parser("uninstall", help=sub["uninstall"])
    uninstall.add_argument("name", help="Extension name.")
    uninstall.add_argument("--strategy", required=True, choices=["purge", "keep-modified", "deactivate"], help="Uninstall strategy: purge, keep-modified, or deactivate.")
    reactivate = subparsers.add_parser("reactivate", help=sub["reactivate"])
    reactivate.add_argument("name", help="Extension name.")
    import_ = subparsers.add_parser("import", help=sub["import"])
    import_.add_argument("path", type=Path, help="Path to extension directory or archive.")
    import_.add_argument("--extensions-dir", type=Path, default=Path("extensions"), help="Extensions directory path.")
    import_.add_argument("--install", action="store_true", help="Install after import.")
    import_.add_argument("--overwrite", action="store_true", help="Overwrite existing extension.")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("name", help="Extension name.")
    export.add_argument("-o", "--file", required=True, type=Path, help="Output archive path.")
    export.add_argument("--handlers-dir", type=Path, help="Handlers directory to include.")
    import_entities = subparsers.add_parser("import-entities", help=sub["import-entities"])
    import_entities.add_argument("-f", "--file", required=True, type=Path, help="Archive file path.")
    export_entities = subparsers.add_parser("export-entities", help=sub["export-entities"])
    export_entities.add_argument("-o", "--file", required=True, type=Path, help="Output archive path.")
    export_entities.add_argument("--entities", required=True, help="Comma-separated entity references <type>:<id>.")
    export_entities.add_argument("--name", required=True, help="Extension name.")
    export_entities.add_argument("--version", required=True, help="Extension version.")


async def dispatch(args: argparse.Namespace) -> object:
    if args.extension_command == "import":
        imported = _extension_import(args.path, args.extensions_dir, overwrite=args.overwrite)
        if not args.install:
            return imported
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.extension_command == "list":
            if args.available and not args.installed:
                return await client.extension_list_available()
            if args.installed and not args.available:
                return await client.extension_list_installed()
            available = (await client.extension_list_available()).get("extensions", [])
            installed = (await client.extension_list_installed()).get("extensions", [])
            return {
                "available": _available_not_installed(available, installed),
                "installed": installed,
            }
        if args.extension_command == "show":
            try:
                return await client.extension_show(args.name)
            except grpc.RpcError:
                return _extension_show_available(args.extensions_dir, args.name)
        if args.extension_command == "install":
            return await client.extension_install(args.name, overwrite=args.overwrite)
        if args.extension_command == "delete":
            return await client.extension_delete(args.name)
        if args.extension_command == "uninstall":
            return await client.extension_uninstall(args.name, args.strategy)
        if args.extension_command == "reactivate":
            return await client.extension_reactivate(args.name)
        if args.extension_command == "import":
            return await client.extension_install(str(imported["name"]))
        if args.extension_command == "export":
            detail = await client.extension_show(args.name)
            exported_entities = []
            for record in _extension_import_records(detail):
                exported_entities.append({
                    "import_path": record["import_path"],
                    "entity": await client.entity_get(record["entity_ref"]),
                })
            handlers_dir = args.handlers_dir or load_system_config(Path("config") / "system.toml").handlers_dir
            warnings = _extension_export(args.file, handlers_dir, args.name, detail, exported_entities)
            return {"exported": args.name, "file": str(args.file), "warnings": warnings}
        if args.extension_command == "export-entities":
            refs = [item.strip() for item in args.entities.split(",") if item.strip()]
            entities = [await client.entity_get(ref) for ref in refs]
            _extension_export_entities(args.file, args.name, args.version, entities)
            return {"exported": args.name, "file": str(args.file), "entities": refs}
        if args.extension_command == "import-entities":
            return await client.extension_import_entities(str(args.file))
        raise ValueError(f"unknown extension command: {args.extension_command}")
    finally:
        await client.close()


def _extension_import(path: Path, extensions_dir: Path, *, overwrite: bool = False) -> dict[str, object]:
    from edera_core.manifest import parse_manifest

    if path.is_dir():
        source = path
        manifest_path = source / "manifest.yaml"
        if not manifest_path.exists():
            raise ValueError("extension import path must contain manifest.yaml")
        manifest = parse_manifest(manifest_path)
        target = extensions_dir / manifest.name
        if target.exists():
            if not overwrite:
                raise ValueError(f"extension already exists: {manifest.name}")
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        return {"imported": True, "name": manifest.name, "path": str(target), "message": f"扩展已导入，使用 'edera extension install {manifest.name}' 安装"}
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp)
        _extract_tar(path, extract_dir)
        candidates = [item.parent for item in extract_dir.rglob("manifest.yaml")]
        if len(candidates) != 1:
            raise ValueError("extension package must contain exactly one manifest.yaml")
        return _extension_import(candidates[0], extensions_dir, overwrite=overwrite)


def _extension_show_available(extensions_dir: Path, name: str) -> dict[str, object]:
    manifest_path = extensions_dir / name / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"extension not found: {name}")
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}


def _available_not_installed(available: object, installed: object) -> list[object]:
    if not isinstance(available, list):
        return []
    if not isinstance(installed, list):
        return available
    installed_names = {item.get("name") for item in installed if isinstance(item, dict)}
    return [item for item in available if not (isinstance(item, dict) and item.get("name") in installed_names)]


def _extension_import_records(detail: dict[str, object]) -> list[dict[str, str]]:
    records = detail.get("import_records")
    if not isinstance(records, list):
        return []
    result: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        import_path = record.get("import_path")
        entity_ref = record.get("entity_ref")
        if isinstance(import_path, str) and import_path and isinstance(entity_ref, str) and entity_ref:
            result.append({"import_path": import_path, "entity_ref": entity_ref})
    return result


def _extension_export(
    path: Path, handlers_dir: Path, name: str, detail: dict[str, object],
    exported_entities: list[dict[str, object]] | None = None,
) -> list[str]:
    manifest = detail.get("manifest") if isinstance(detail.get("manifest"), dict) else detail
    warnings: list[str] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        root.mkdir()
        (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if isinstance(manifest, dict) and manifest.get("type") == "workflow_extension":
            warnings.extend(_export_workflow_artifacts(root, handlers_dir, name, manifest))
        elif (handlers_dir / name).exists() and (handlers_dir / name).is_dir():
            shutil.copytree(handlers_dir / name, root, dirs_exist_ok=True)
        elif _manifest_handler_entries(manifest):
            warnings.append(f"handler code not included: {handlers_dir / name} is missing")
        for entry in _manifest_handler_entries(manifest):
            relative = Path(entry)
            if relative.is_absolute() or ".." in relative.parts:
                warnings.append(f"handler code not included: {entry} is outside handlers/")
        for item in exported_entities or []:
            import_path = item.get("import_path")
            entity = item.get("entity")
            if not isinstance(import_path, str) or not isinstance(entity, dict):
                continue
            _write_package_entity_yaml(root, import_path, _entity_document(entity))
        import_records = detail.get("import_records")
        if isinstance(import_records, list):
            (root / "import_records.json").write_text(json.dumps(import_records, ensure_ascii=False), encoding="utf-8")
        import tarfile as tarfile_mod
        with tarfile_mod.open(path, "w:gz") as archive:
            archive.add(root, arcname=root.name)
    return warnings


def _export_workflow_artifacts(root: Path, handlers_dir: Path, name: str, manifest: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    for handler in _workflow_provider_packages(manifest, name):
        package = handler["package"]
        source = handlers_dir / package
        provider = package.removeprefix(f"{name}.")
        if not source.exists():
            warnings.append(f"provider code not included: {source} is missing")
            continue
        target = root / "_providers" / provider
        shutil.copytree(source, target, dirs_exist_ok=True)
        manifest_path = target / "manifest.yaml"
        if not manifest_path.exists():
            provider_manifest = _provider_manifest(manifest, provider, package)
            manifest_path.write_text(yaml.safe_dump(provider_manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for item in _manifest_library_imports(manifest):
        library_name = Path(item).name
        source = _workflow_library_source(handlers_dir, name, library_name)
        if source is None:
            warnings.append(f"library code not included: {handlers_dir / '_libs' / f'{name}.{library_name}'} is missing")
            continue
        target = root / "_lib" / library_name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return warnings


def _workflow_provider_packages(manifest: dict[str, object], name: str) -> list[dict[str, str]]:
    packages = _manifest_handler_packages(manifest)
    providers = _manifest_provider_names(manifest)
    if not providers:
        return packages
    expected = {f"{name}.{provider}" for provider in providers}
    return [item for item in packages if item["package"] in expected]


def _manifest_provider_names(manifest: dict[str, object]) -> list[str]:
    imports = manifest.get("imports")
    providers = imports.get("providers") if isinstance(imports, dict) else None
    if not isinstance(providers, list):
        return []
    result: list[str] = []
    for item in providers:
        if not isinstance(item, str):
            continue
        parts = Path(item).parts
        if len(parts) >= 3 and parts[-1] == "manifest.yaml" and "*" not in parts[-2]:
            result.append(parts[-2])
    return result


def _provider_manifest(manifest: dict[str, object], provider: str, package: str) -> dict[str, object]:
    result: dict[str, object] = {
        "name": provider,
        "version": str(manifest.get("version") or ""),
        "handlers": [_provider_handler(handler, package) for handler in _manifest_provider_handlers(manifest, package)],
    }
    libraries = _manifest_library_imports(manifest)
    if libraries:
        result["depends"] = libraries
    return result


def _manifest_provider_handlers(manifest: dict[str, object], package: str) -> list[dict[str, object]]:
    handlers = manifest.get("handlers")
    if not isinstance(handlers, list):
        return []
    return [handler for handler in handlers if isinstance(handler, dict) and handler.get("package") == package]


def _provider_handler(handler: dict[str, object], package: str) -> dict[str, object]:
    prefix = f"{package}."
    name = str(handler.get("name") or "")
    result: dict[str, object] = {"name": name.removeprefix(prefix)}
    for key in ("entry", "role", "input_type", "output_type", "timeout_seconds"):
        if key in handler:
            result[key] = handler[key]
    return result


def _workflow_library_source(handlers_dir: Path, extension_name: str, library_name: str) -> Path | None:
    for source in (
        handlers_dir / "_libs" / f"{extension_name}.{library_name}",
        handlers_dir.parent / "libs" / f"{extension_name}.{library_name}",
    ):
        if source.exists():
            return source
    return None


def _manifest_handler_packages(manifest: dict[str, object]) -> list[dict[str, str]]:
    handlers = manifest.get("handlers")
    if not isinstance(handlers, list):
        return []
    packages: list[dict[str, str]] = []
    seen: set[str] = set()
    for handler in handlers:
        if not isinstance(handler, dict):
            continue
        package = handler.get("package")
        if not isinstance(package, str) or "." not in package or package in seen:
            continue
        seen.add(package)
        packages.append({"package": package})
    return packages


def _manifest_library_imports(manifest: dict[str, object]) -> list[str]:
    imports = manifest.get("imports")
    libraries = imports.get("libraries") if isinstance(imports, dict) else None
    return [item for item in libraries if isinstance(item, str)] if isinstance(libraries, list) else []


def _manifest_handler_entries(manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    handlers = manifest.get("handlers")
    if not isinstance(handlers, list):
        return []
    entries: list[str] = []
    for handler in handlers:
        if isinstance(handler, dict) and isinstance(handler.get("entry"), str):
            entries.append(str(handler["entry"]))
        elif isinstance(handler, str):
            entries.append(handler)
    return entries


def _write_package_entity_yaml(root: Path, import_path: str, document: dict[str, object]) -> None:
    relative = Path(import_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe extension import path")
    _write_entity_yaml(root / relative, document)


def _extension_export_entities(path: Path, name: str, version: str, entities: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        entity_dir = root / "entities"
        entity_dir.mkdir(parents=True)
        imports: list[str] = []
        for entity in entities:
            entity_type = str(entity.get("type") or "")
            entity_id = str(entity.get("id") or "")
            if not entity_type or not entity_id:
                raise ValueError("entity response must include type and id")
            import_path = f"entities/{entity_type}-{entity_id}.yaml"
            imports.append(import_path)
            document = {"type": entity_type, "id": entity_id, "attributes": entity.get("attributes") or {}}
            (root / import_path).write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
        manifest = {"name": name, "version": version, "imports": {"entities": imports}}
        (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
        import tarfile as tarfile_mod
        with tarfile_mod.open(path, "w:gz") as archive:
            archive.add(root, arcname=root.name)


def _extract_tar(path: Path, target: Path) -> None:
    import tarfile as tarfile_mod
    if not path.is_file():
        raise FileNotFoundError(path)
    with tarfile_mod.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("unsafe extension package path")
        archive.extractall(target)
