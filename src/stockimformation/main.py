from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from stockimformation.config.loader import load_app_config
from stockimformation.dag.loader import load_graph
from stockimformation.dag.runner import DagRunner
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation.models import create_engine, init_db, session_factory
from stockimformation.models.entities import Advice, AnalysisResult, Briefing, RawItem
from stockimformation.models.repository import store_cycle_outputs
from stockimformation.node.models import NodeOutput
from stockimformation.node.executor import NodeExecutor
from stockimformation.services import (
    analyze_handler,
    make_advice_handler,
    make_briefing_handler,
    make_fetch_handler,
    make_notify_handler,
)


def build_executor(config_dir: Path = Path("config")) -> tuple[NodeExecutor, str]:
    app_config = load_app_config(config_dir)
    handlers = {
        "fetch-rss": make_fetch_handler(app_config.portfolio, "rss"),
        "fetch-web": make_fetch_handler(app_config.portfolio, "web"),
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(app_config.portfolio),
        "generate-briefing": make_briefing_handler(app_config.portfolio),
        "notify-ntfy": make_notify_handler(app_config.runtime),
    }
    executor = NodeExecutor(app_config.nodes, app_config.system, app_config.runtime, handlers)
    return executor, "default"


async def run_default_cycle(config_dir: Path = Path("config")) -> object:
    app_config = load_app_config(config_dir)
    engine = create_engine(app_config.system.database_url)
    await init_db(engine)
    handlers = {
        "fetch-rss": make_fetch_handler(app_config.portfolio, "rss"),
        "fetch-web": make_fetch_handler(app_config.portfolio, "web"),
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(app_config.portfolio),
        "generate-briefing": make_briefing_handler(app_config.portfolio),
        "notify-ntfy": make_notify_handler(app_config.runtime),
    }
    executor = NodeExecutor(app_config.nodes, app_config.system, app_config.runtime, handlers)
    graph = load_graph(app_config.dags["default"], app_config.nodes)
    source_names = [source.name for source in app_config.portfolio.sources]
    result = await DagRunner(executor).run(
        graph,
        cycle_id=uuid4().hex,
        initial_payload={"source_names": source_names},
    )
    await _persist_outputs(session_factory(engine), result.node_outputs)
    return result.payload


async def _persist_outputs(
    factory: async_sessionmaker[AsyncSession],
    outputs: Mapping[str, NodeOutput],
) -> None:
    raw_payload = _list_payload(outputs, "rss-fetcher") + _list_payload(outputs, "web-scraper")
    analyses_payload = _list_payload(outputs, "reader")
    advices_payload = _list_payload(outputs, "advisor")
    briefing_payload = _dict_payload(outputs, "briefing-generator")
    raw_items = [RawItem.model_validate(item) for item in raw_payload]
    analyses = [AnalysisResult.model_validate(item) for item in analyses_payload]
    advices = [Advice.model_validate(item) for item in advices_payload]
    briefing = Briefing.model_validate(briefing_payload) if briefing_payload else None
    async with factory() as session:
        await store_cycle_outputs(session, raw_items, analyses, advices, briefing)
        await session.commit()


def _list_payload(outputs: Mapping[str, NodeOutput], node_name: str) -> list[object]:
    output = outputs.get(node_name)
    if output is None or not output.ok:
        return []
    return output.payload if isinstance(output.payload, list) else []


def _dict_payload(outputs: Mapping[str, NodeOutput], node_name: str) -> dict[str, object]:
    output = outputs.get(node_name)
    if output is None or not output.ok:
        return {}
    return output.payload if isinstance(output.payload, dict) else {}


async def serve(config_dir: Path = Path("config")) -> None:
    app_config = load_app_config(config_dir)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_default_cycle,
        "interval",
        minutes=app_config.system.schedule_minutes,
        args=[config_dir],
        id="default-dag",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    await run_default_cycle(config_dir)
    while True:
        await asyncio.sleep(3600)


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
