from __future__ import annotations

import json
import subprocess

from edera_testing import FakePIBinary, MockScript


def test_fake_pi_binary_output(tmp_path) -> None:
    binary = FakePIBinary(output={"result": "success"}).write(tmp_path)

    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    assert json.loads(result.stdout) == {"result": "success"}


def test_fake_pi_binary_exit_code(tmp_path) -> None:
    binary = FakePIBinary(exit_code=7).write(tmp_path)

    result = subprocess.run([str(binary)], capture_output=True, text=True)

    assert result.returncode == 7


def test_mock_script(tmp_path) -> None:
    script = MockScript("def main(ticker):\n    return {'ticker': ticker}\n").write(tmp_path)

    namespace: dict[str, object] = {}
    exec(script.read_text(), namespace)

    assert namespace["main"]("AAPL") == {"ticker": "AAPL"}
