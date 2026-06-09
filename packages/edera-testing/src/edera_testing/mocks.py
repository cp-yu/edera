from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FakePIBinary:
    def __init__(
        self,
        *,
        output: Any | None = None,
        exit_code: int = 0,
        script: str | None = None,
        filename: str = "pi",
    ) -> None:
        self.output = {} if output is None else output
        self.exit_code = exit_code
        self.script = script
        self.filename = filename

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.filename
        path.write_text(self.script or self._script(), encoding="utf-8")
        path.chmod(0o755)
        return path

    def _script(self) -> str:
        output = json.dumps(self.output)
        return (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "record = {'argv': sys.argv, 'cwd': os.getcwd(), 'environ': dict(os.environ)}\n"
            "with Path('pi-calls.jsonl').open('a', encoding='utf-8') as f:\n"
            "    f.write(json.dumps(record, sort_keys=True) + '\\n')\n"
            f"print({output!r})\n"
            f"raise SystemExit({self.exit_code})\n"
        )


class MockScript:
    def __init__(self, source: str, filename: str = "mock_script.py") -> None:
        self.source = source
        self.filename = filename

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.filename
        path.write_text(self.source, encoding="utf-8")
        return path
