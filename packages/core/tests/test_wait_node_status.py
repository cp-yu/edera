from __future__ import annotations

from edera_core.storage.entities import NodeRun


def test_waiting_status_is_valid() -> None:
    run = NodeRun(run_id="run", node_name="gate", status="waiting")

    assert run.status == "waiting"


def test_wait_timeout_failure_kind_is_valid() -> None:
    run = NodeRun(run_id="run", node_name="gate", status="failed", failure_kind="wait_timeout")

    assert run.failure_kind == "wait_timeout"
