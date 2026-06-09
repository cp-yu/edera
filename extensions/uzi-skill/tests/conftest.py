from __future__ import annotations

from pathlib import Path

import pytest

from edera_testing import extension_runtime, mock_handler_context

_PROJECT_ROOT = Path(__file__).parents[3]


@pytest.fixture
def extension_name() -> str:
    return "uzi-skill"


@pytest.fixture(autouse=True)
def project_root_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_PROJECT_ROOT)
