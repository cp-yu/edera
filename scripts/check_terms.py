from __future__ import annotations

from pathlib import Path


ROOTS = (
    Path("openspec/specs"),
    Path("openspec/project.opsx.yaml"),
    Path("openspec/project.opsx.relations.yaml"),
    Path("packages/core/src"),
    Path("packages/core/tests"),
    Path("packages/core-types/src"),
    Path("tests/core"),
    Path("tests/extensions"),
    Path("extensions"),
    Path("apps/web-console/src"),
    Path("apps/web-console/scripts"),
    Path("apps/web-console/tests"),
    Path("config"),
    Path("scripts"),
    Path("docs"),
    Path("README.md"),
    Path("GLOSSARY.md"),
    Path("todo.md"),
    Path("useful.md"),
    Path("_bmad-output"),
)

SUFFIXES = {".html", ".md", ".py", ".ts", ".tsx", ".mjs", ".yaml", ".yml", ".json", ".proto"}
FORBIDDEN = {
    "pipeline" + "_runs": "dag_runs",
    "cycle" + "_id": "run_id",
    "Pipeline" + "Service": "DagService/EventService/SystemService",
    "Pipeline" + "Run": "DagRun",
    "Pipeline" + "Controller": "DagController",
    "Dag" + "Trigger" + "Request": "DagRunRequest",
    "dag " + "trigger": "dag run",
    "trigger " + "emit": "event emit",
    "/api/" + "pipeline": "/api/dags",
    "pipeline" + "_emit": "event_emit",
    "dag" + "_trigger": "dag_run",
    "edera_core." + "pipeline": "edera_core.dag_controller",
    "trigger" + "-emit-rpc": "event-emit-rpc",
    "run_default_cycle": "run_default_run",
    "test_empty_cycle_status_notification": "test_empty_run_status_notification",
    "test_retry_cycle_not_found": "test_retry_run_not_found",
    "test_resolve_sandbox_cycle_session_dir": "test_resolve_sandbox_run_session_dir",
    "origin_cycle": "origin_run",
    "_latest_cycle": "_latest_run",
    "api_pipeline_": "api_dag_ or api_system_",
    "pipeline_status": "dag_status",
    "cycle briefing": "run briefing",
    "uq_edge_inputs_cycle_edge": "uq_edge_inputs_run_edge",
    "uq_source_recoveries_cycle_node_source": "uq_source_recoveries_run_node_source",
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "dist",
    "build",
}
SKIP_PATH_PREFIXES = (
    Path("openspec/changes/archive"),
    Path("openspec/changes/terminology-unification"),
    Path("alembic/versions"),
)
SKIP_PATHS = {Path("scripts/check_terms.py")}
LINE_ALLOWLIST = {
    (Path("GLOSSARY.md"), " | cycle_id |"),
    (Path("GLOSSARY.md"), " | PipelineService |"),
    (Path("GLOSSARY.md"), " | PipelineRun |"),
    (Path("GLOSSARY.md"), " | PipelineController |"),
}


def _iter_files(root: Path):
    if root.is_file():
        yield root
        return
    if not root.exists():
        return
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def _skipped(path: Path) -> bool:
    return path in SKIP_PATHS or any(path == prefix or prefix in path.parents for prefix in SKIP_PATH_PREFIXES)


def main() -> int:
    failures: list[str] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for path in _iter_files(root):
            if _skipped(path) or path.suffix not in SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for forbidden, replacement in FORBIDDEN.items():
                for line in text.splitlines():
                    if forbidden in line and (path, f" | {forbidden} |") not in LINE_ALLOWLIST:
                        failures.append(f"{path}: use {replacement} instead of {forbidden}")
    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
