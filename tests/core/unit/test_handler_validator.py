import subprocess
from pathlib import Path
import json

from edera_core.handler_validator import validate_handler


def test_valid_handler(tmp_path: Path) -> None:
    p = tmp_path / "ok.py"
    p.write_text("async def run(ctx):\n    return {}\n", encoding="utf-8")
    assert validate_handler(p) == []


def test_missing_run(tmp_path: Path) -> None:
    p = tmp_path / "missing.py"
    p.write_text("async def other(ctx):\n    return {}\n", encoding="utf-8")
    assert validate_handler(p) == ["missing async def run"]


def test_sync_not_async(tmp_path: Path) -> None:
    p = tmp_path / "sync.py"
    p.write_text("def run(ctx):\n    return {}\n", encoding="utf-8")
    assert "run must be async def" in validate_handler(p)


def test_wrong_param_count(tmp_path: Path) -> None:
    p = tmp_path / "two_params.py"
    p.write_text("async def run(a, b):\n    return {}\n", encoding="utf-8")
    assert "run must accept exactly 1 parameter" in validate_handler(p)


def test_zero_params(tmp_path: Path) -> None:
    p = tmp_path / "zero_params.py"
    p.write_text("def run():\n    return {}\n", encoding="utf-8")
    errors = validate_handler(p)
    assert "run must be async def" in errors
    assert "run must accept exactly 1 parameter" in errors


def test_syntax_error(tmp_path: Path) -> None:
    p = tmp_path / "bad.py"
    p.write_text("def run(:\n    return {}\n", encoding="utf-8")
    assert validate_handler(p)[0].startswith("syntax error:")


def test_posonly_param(tmp_path: Path) -> None:
    p = tmp_path / "posonly.py"
    p.write_text("async def run(ctx, /):\n    return {}\n", encoding="utf-8")
    assert validate_handler(p) == []


def test_vararg(tmp_path: Path) -> None:
    p = tmp_path / "vararg.py"
    p.write_text("async def run(ctx, *rest):\n    return {}\n", encoding="utf-8")
    assert "run must accept exactly 1 parameter" in validate_handler(p)


def test_kwarg(tmp_path: Path) -> None:
    p = tmp_path / "kwarg.py"
    p.write_text("async def run(ctx, **kw):\n    return {}\n", encoding="utf-8")
    assert "run must accept exactly 1 parameter" in validate_handler(p)


def test_required_kwonly(tmp_path: Path) -> None:
    p = tmp_path / "req_kwonly.py"
    p.write_text("async def run(ctx, *, extra):\n    return {}\n", encoding="utf-8")
    assert "run must accept exactly 1 parameter" in validate_handler(p)


def test_optional_kwonly(tmp_path: Path) -> None:
    p = tmp_path / "opt_kwonly.py"
    p.write_text("async def run(ctx, *, extra=None):\n    return {}\n", encoding="utf-8")
    assert "run must accept exactly 1 parameter" in validate_handler(p)


def test_no_code_execution(tmp_path: Path) -> None:
    p = tmp_path / "safe.py"
    p.write_text(
        "import os; os.system('echo pwned > /tmp/validator_test')\n"
        "async def run(ctx):\n    return {}\n",
        encoding="utf-8",
    )
    assert validate_handler(p) == []
    assert not Path("/tmp/validator_test").exists()


def test_cli_integration(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text("async def run(node_input):\n    return {}\n", encoding="utf-8")
    result = subprocess.run(
        ["uv", "run", "edera", "handler-validate", str(good)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(result.stdout) == {"ok": True}
