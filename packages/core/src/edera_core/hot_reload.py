from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig
from edera_core.node.executor import NodeExecutor


ReloadCallback = Callable[[AppConfig, BootstrapResult], Awaitable[None]]
EmitCallback = Callable[[str], Awaitable[object]]
ConfigLoader = Callable[[], AppConfig | Awaitable[AppConfig]]
BootstrapLoader = Callable[[], BootstrapResult | Awaitable[BootstrapResult]]
LOGGER = logging.getLogger(__name__)


class HotReloader:
    def __init__(
        self,
        config_dir: Path,
        extensions_dirs: list[Path],
        callback: ReloadCallback,
        config_loader: ConfigLoader,
        bootstrap_loader: BootstrapLoader,
        emit: EmitCallback | None = None,
        debounce_seconds: float = 0.2,
    ) -> None:
        self.config_dir = config_dir
        self.extensions_dirs = extensions_dirs
        self.callback = callback
        self.emit = emit
        self.config_loader = config_loader
        self.bootstrap_loader = bootstrap_loader
        self.debounce_seconds = debounce_seconds

    async def reload_once(self) -> None:
        loaded = self.config_loader()
        config = await loaded if inspect.isawaitable(loaded) else loaded
        loaded_bootstrap = self.bootstrap_loader()
        bootstrap = await loaded_bootstrap if inspect.isawaitable(loaded_bootstrap) else loaded_bootstrap
        await self.callback(config, bootstrap)
        if self.emit is not None:
            await self.emit("event:config-changed")

    async def watch(self) -> None:
        from watchfiles import awatch

        roots = [root for root in [self.config_dir, *self.extensions_dirs] if root.exists()]
        if not roots:
            await asyncio.Event().wait()
            return
        async for _changes in awatch(*roots, debounce=int(self.debounce_seconds * 1000)):
            try:
                await self.reload_once()
            except Exception:
                LOGGER.exception("hot reload failed")


def clear_handler_cache(executor: NodeExecutor) -> None:
    executor._modules.clear()
