import asyncio
import sys
from pathlib import Path
from stockimformation_core.config.loader import load_app_config
from stockimformation_core.handler_validator import validate_handler
from stockimformation_core.pipeline import PipelineController
from stockimformation_core.web.app import create_app


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
    if len(sys.argv) >= 3 and sys.argv[1] == "handler-validate":
        errors = validate_handler(Path(sys.argv[2]))
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print("ok")
        return
    asyncio.run(serve())


if __name__ == "__main__":
    main()
