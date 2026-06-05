from __future__ import annotations

from pathlib import Path

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig
from edera_core.dag_controller import DagController
from edera_core.registry import EntityTypeRegistry, HandlerRegistry


class Engine:
    def __init__(self, config_dir: Path = Path("config"), extensions_dirs: list[Path] | None = None) -> None:
        self.config_dir = config_dir
        self.extensions_dirs = extensions_dirs or [Path("extensions")]
        self.bootstrap = BootstrapResult(HandlerRegistry().seal(), EntityTypeRegistry(), [], {}, {}, {})
        self.config: AppConfig | None = None
        self.controller = DagController(self.config_dir, extensions_dirs=self.extensions_dirs)

    async def start(self, run_startup: bool = False) -> None:
        await self.controller.start(run_startup=run_startup)
        try:
            snapshot = self.controller.runtime_snapshot()
        except RuntimeError:
            return
        self.bootstrap = snapshot.bootstrap
        self.config = snapshot.config

    async def run(self, source: str = "manual", dag_name: str = "default") -> str:
        return await self.controller.run_now(source, dag_name)

    async def shutdown(self) -> None:
        await self.controller.shutdown()
