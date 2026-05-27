from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from edera_core.bootstrap import BootstrapResult, scan_extensions
from edera_core.config.loader import load_app_config
from edera_core.config.schema import AppConfig
from edera_core.node.executor import NodeExecutor


ReloadCallback = Callable[[AppConfig, BootstrapResult], Awaitable[None]]


class HotReloader:
    def __init__(
        self,
        config_dir: Path,
        extensions_dirs: list[Path],
        callback: ReloadCallback,
        debounce_seconds: float = 0.2,
    ) -> None:
        self.config_dir = config_dir
        self.extensions_dirs = extensions_dirs
        self.callback = callback
        self.debounce_seconds = debounce_seconds

    async def reload_once(self) -> None:
        config = load_app_config(self.config_dir)
        bootstrap = scan_extensions(self.extensions_dirs, self.config_dir)
        config.entity_types.update(bootstrap.entity_type_registry.as_dict())
        await self.callback(config, bootstrap)

    async def watch(self) -> None:
        from watchfiles import awatch

        roots = [self.config_dir, *self.extensions_dirs]
        async for _changes in awatch(*roots, debounce=int(self.debounce_seconds * 1000)):
            await self.reload_once()


def clear_handler_cache(executor: NodeExecutor) -> None:
    executor._modules.clear()
