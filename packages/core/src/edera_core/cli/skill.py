from __future__ import annotations

import argparse
from pathlib import Path

from edera_core.cli._common import (
    _skill_dir_payload,
    _skill_files_from_payload,
    _skill_from_list,
    _write_skill_files,
)
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage the skill registry (技能).",
    help_line="Manage skills (技能)",
    epilog=_fmt_epilog(
        "A skill bundles a YAML manifest plus handler assets, importable from a directory.",
        [
            ("edera skill list", "list installed skills"),
            ("edera skill import-dir ./skills/my-skill", "register a skill from a directory"),
            ("edera skill export my-skill -o ./out", "export a skill to a directory"),
        ],
    ),
    subcommands={
        "list": "List installed skills.",
        "show": "Show a single skill by name.",
        "create": "Register a skill from a source directory.",
        "update": "Replace an existing skill from a source directory.",
        "import-dir": "Register a skill from a directory (alias of create).",
        "import-batch": "Register multiple skills from a parent directory.",
        "export": "Export a skill to an output directory.",
        "delete": "Delete a skill by name.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="skill_command", required=True)
    sub = HELP.subcommands
    subparsers.add_parser("list", help=sub["list"])
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name", help="Skill name.")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("--from-dir", required=True, type=Path, help="Source directory containing SKILL.md.")
    update = subparsers.add_parser("update", help=sub["update"])
    update.add_argument("name", help="Skill name.")
    update.add_argument("--from-dir", required=True, type=Path, help="Source directory containing SKILL.md.")
    import_dir = subparsers.add_parser("import-dir", help=sub["import-dir"])
    import_dir.add_argument("path", type=Path, help="Path to skill directory.")
    import_batch = subparsers.add_parser("import-batch", help=sub["import-batch"])
    import_batch.add_argument("path", type=Path, help="Parent directory containing skill subdirectories.")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("name", help="Skill name.")
    export.add_argument("-o", "--output-dir", required=True, type=Path, help="Output directory path.")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("name", help="Skill name.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.skill_command == "list":
            return await client.graph_list_skills()
        if args.skill_command == "show":
            return _skill_from_list(await client.graph_list_skills(), args.name)
        if args.skill_command == "create":
            return await client.graph_create_skill(_skill_dir_payload(args.from_dir))
        if args.skill_command == "update":
            return await client.graph_save_skill(args.name, {**_skill_dir_payload(args.from_dir), "name": args.name})
        if args.skill_command == "import-dir":
            payload = _skill_dir_payload(args.path)
            return await client.graph_save_skill(str(payload["name"]), payload)
        if args.skill_command == "import-batch":
            imported = []
            for path in sorted(item for item in args.path.iterdir() if item.is_dir() and (item / "SKILL.md").is_file()):
                payload = _skill_dir_payload(path)
                result = await client.graph_save_skill(str(payload["name"]), payload)
                skill = result.get("skill") if isinstance(result, dict) else None
                if isinstance(skill, dict) and isinstance(skill.get("name"), str):
                    imported.append(skill["name"])
            return {"imported": imported}
        if args.skill_command == "export":
            skill = _skill_from_list(await client.graph_list_skills(), args.name)
            target = args.output_dir / args.name
            _write_skill_files(target, _skill_files_from_payload(skill))
            return {"exported": args.name, "path": str(target)}
        if args.skill_command == "delete":
            return await client.graph_delete_skill(args.name)
    finally:
        await client.close()
    raise ValueError(f"unknown skill command: {args.skill_command}")
_grpc_skill = dispatch
