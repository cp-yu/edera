from __future__ import annotations

import argparse
from pathlib import Path

import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Validate a handler module on disk without contacting the server.",
    help_line="Validate a handler module (offline)",
    epilog=_fmt_epilog(
        "Runs schema validation directly against a handler file; does not need a running server.",
        [
            ("edera handler-validate ./handlers/my-handler.yaml", "validate a handler definition"),
        ],
    ),
    subcommands={},
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, help="Path to handler YAML file.")


def dispatch(args: argparse.Namespace) -> object:  # noqa: F811 - sync dispatch
    errors = _cli.validate_handler(args.path)
    if errors:
        raise ValueError("\n".join(errors))
    return {"ok": True}
