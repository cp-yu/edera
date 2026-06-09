from __future__ import annotations

import pytest

from edera_testing import extension_runtime, mock_handler_context, mock_pi_binary


@pytest.fixture
def extension_name() -> str:
    return "default-news-workflow"
