from __future__ import annotations

from pathlib import Path

from stockimformation_core.bootstrap import BootstrapResult, scan_extensions
from stockimformation_core.config.loader import load_app_config
from stockimformation_core.config.schema import AppConfig
from stockimformation_core.pipeline import PipelineController


class Engine:
    def __init__(self, config_dir: Path = Path("config"), extensions_dirs: list[Path] | None = None) -> None:
        self.config_dir = config_dir
        self.extensions_dirs = extensions_dirs or [Path("extensions")]
        self.bootstrap: BootstrapResult = scan_extensions(self.extensions_dirs, self.config_dir)
        self.config: AppConfig = load_app_config(self.config_dir)
        self.config.entity_types.update(self.bootstrap.entity_type_registry.as_dict())
        self.controller = PipelineController(self.config_dir, extensions_dirs=self.extensions_dirs)

    async def start(self, run_startup: bool = False) -> None:
        await self.controller.start(run_startup=run_startup)

    async def run(self, trigger: str = "manual", dag_name: str = "default") -> str:
        return await self.controller.run_now(trigger, dag_name)

    async def shutdown(self) -> None:
        await self.controller.shutdown()
