from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from edera_core.pipeline import PipelineController


def main() -> None:
    parser = argparse.ArgumentParser(prog="edera_core.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--once", action="store_true")
    run.add_argument("--dag", default="default")
    run.add_argument("--config-dir", default="config")
    args = parser.parse_args()
    if args.command == "run" and args.once:
        asyncio.run(_run_once(Path(args.config_dir), args.dag))
        return
    parser.error("only 'run --once' is supported")


async def _run_once(config_dir: Path, dag_name: str) -> None:
    controller = PipelineController(config_dir)
    await controller.start(run_startup=False)
    try:
        cycle_id = await controller.run_now("manual", dag_name)
        print(f"pipeline run completed: {cycle_id}")
    finally:
        await controller.shutdown()


if __name__ == "__main__":
    main()
