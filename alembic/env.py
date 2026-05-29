from logging.config import fileConfig
from pathlib import Path
from urllib.parse import urlparse

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from edera_core.storage.entities import EmitRecord, EventGroupBit, NodeOutputEntity, NodeRun, PipelineRun

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _ensure_sqlite_parent(config.get_main_option("sqlalchemy.url"))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


def _ensure_sqlite_parent(url: str | None) -> None:
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme != "sqlite" or parsed.path in {"", ":memory:"}:
        return
    db_path = Path(parsed.path.lstrip("/"))
    db_path.parent.mkdir(parents=True, exist_ok=True)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


__all__ = ["EmitRecord", "EventGroupBit", "NodeOutputEntity", "NodeRun", "PipelineRun"]
