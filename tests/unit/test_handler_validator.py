import subprocess
from pathlib import Path

from stockimformation.handler_validator import validate_handler


def test_handler_validator(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    bad_signature = tmp_path / "bad_signature.py"
    bad_syntax = tmp_path / "bad_syntax.py"
    good.write_text("async def run(node_input):\n    return {}\n", encoding="utf-8")
    bad_signature.write_text("def run():\n    return {}\n", encoding="utf-8")
    bad_syntax.write_text("def run(:\n    return {}\n", encoding="utf-8")

    assert validate_handler(good) == []
    assert validate_handler(bad_signature) == ["run must accept 1 or 3 parameters"]
    assert validate_handler(bad_syntax)[0].startswith("syntax error:")

    result = subprocess.run(
        ["uv", "run", "stockimformation", "handler-validate", str(good)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.stdout.strip() == "ok"
