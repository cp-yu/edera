import asyncio
import argparse
import sys
from pathlib import Path
from edera_core.bootstrap import scan_extensions
from edera_core.config.loader import load_app_config
from edera_core.handler_validator import validate_handler
from edera_core.pipeline import PipelineController
from edera_core.web.app import create_app


async def serve(config_dir: Path = Path("config")) -> None:
    import uvicorn

    app_config = load_app_config(config_dir)
    if app_config.system.web_host != "127.0.0.1":
        raise ValueError("web_host must be 127.0.0.1")
    bootstrap = scan_extensions([config_dir.parent / "extensions"], config_dir)
    controller = PipelineController(config_dir)
    app = create_app(
        config_dir=config_dir,
        controller=controller,
        handler_registry=bootstrap.handler_registry,
    )
    config = uvicorn.Config(
        app,
        host=app_config.system.web_host,
        port=app_config.system.web_port,
        log_level=app_config.system.log_level.lower(),
    )
    await uvicorn.Server(config).serve()


def main() -> None:
    parser = argparse.ArgumentParser(prog="edera")
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    subparsers = parser.add_subparsers(dest="command")
    validate = subparsers.add_parser("handler-validate")
    validate.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "handler-validate":
        errors = validate_handler(args.path)
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print("ok")
        return
    asyncio.run(serve(args.config_dir))


if __name__ == "__main__":
    main()
