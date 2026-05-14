import asyncio
from pathlib import Path
from stockimformation.config.loader import load_app_config
from stockimformation.pipeline import PipelineController
from stockimformation.web.app import create_app


async def serve(config_dir: Path = Path("config")) -> None:
    import uvicorn

    app_config = load_app_config(config_dir)
    if app_config.system.web_host != "127.0.0.1":
        raise ValueError("web_host must be 127.0.0.1")
    controller = PipelineController(config_dir)
    app = create_app(config_dir=config_dir, controller=controller)
    config = uvicorn.Config(
        app,
        host=app_config.system.web_host,
        port=app_config.system.web_port,
        log_level=app_config.system.log_level.lower(),
    )
    await uvicorn.Server(config).serve()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
