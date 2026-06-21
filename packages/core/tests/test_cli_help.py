from __future__ import annotations

import pytest

from edera_core import cli
from edera_core.cli_help import COMMANDS


def _run_main(argv: list[str], monkeypatch, capsys) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.argv", ["edera", *argv])
    try:
        cli.main()
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
    else:
        code = 0
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_top_level_help_contains_description_and_examples(monkeypatch, capsys):
    code, out, _ = _run_main(["--help"], monkeypatch, capsys)
    assert code == 0
    assert "Edera CLI" in out
    assert "EXAMPLES" in out
    for name in COMMANDS:
        assert name in out


def test_top_level_help_groups_global_options(monkeypatch, capsys):
    code, out, _ = _run_main(["--help"], monkeypatch, capsys)
    assert code == 0
    assert "Connection:" in out
    assert "Output:" in out
    common_idx = out.index("Common:")
    assert "-h, --help" in out[common_idx:]
    assert "--version" in out[common_idx:]


def test_first_level_help_contains_description_and_examples(monkeypatch, capsys):
    for command in ("entity", "dag", "client"):
        code, out, _ = _run_main([command, "--help"], monkeypatch, capsys)
        assert code == 0, f"{command} --help exited with {code}"
        assert COMMANDS[command].description.split("(")[0].strip() in out
        assert "EXAMPLES" in out


def test_handler_validate_help(monkeypatch, capsys):
    code, out, _ = _run_main(["handler-validate", "--help"], monkeypatch, capsys)
    assert code == 0
    assert "Validate a handler module" in out
    assert "EXAMPLES" in out


def test_second_level_help_contains_argument_help(monkeypatch, capsys):
    code, out, _ = _run_main(["entity", "get", "--help"], monkeypatch, capsys)
    assert code == 0
    assert "usage:" in out
    assert "ref" in out
    assert "Entity reference" in out


def test_unknown_command_exits_nonzero(monkeypatch, capsys):
    code, _, err = _run_main(["nope"], monkeypatch, capsys)
    assert code != 0
    assert "usage:" in err or "usage:" in capsys.readouterr().out
