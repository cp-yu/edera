from __future__ import annotations

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.trigger import TriggerExpressionError, TriggerExecutor, parse_trigger_expression

import pytest


def test_expression_parses_boolean_groups() -> None:
    expr = parse_trigger_expression('cron:"0 9 * * *" AND (event:market-open OR event:breaking-news)')

    assert expr.tokens == ['cron:"0 9 * * *"', "event:breaking-news", "event:market-open"]
    assert expr.evaluate({'cron:"0 9 * * *"', "event:market-open"})
    assert not expr.evaluate({"event:market-open"})


def test_invalid_cron() -> None:
    with pytest.raises(TriggerExpressionError):
        parse_trigger_expression("cron:0 9 * * *")


def test_manual_prefix_rejected_in_expression() -> None:
    with pytest.raises(TriggerExpressionError, match="manual prefix"):
        parse_trigger_expression("manual:dag:default")


@pytest.mark.asyncio
async def test_reverse_index() -> None:
    executor = TriggerExecutor(
        EntityStore(_triggers(), _types(), EntityRelationsConfig()),
    )

    index = executor.reverse_index()

    assert [trigger.id for trigger in index["event:price-drop"]] == ["price"]
    assert [trigger.id for trigger in index['cron:"0 9 * * *"']] == ["morning"]


def _types() -> dict[str, EntityTypeConfig]:
    return {
        "trigger": EntityTypeConfig.model_validate(
            {
                "display_name": "Trigger",
                "business_id_field": "name",
                "display_template": "{name}",
                "schema": {
                    "required": ["name", "wait_for", "target"],
                    "properties": {
                        "name": {"type": "string"},
                        "wait_for": {"type": "string"},
                        "target": {"type": "string"},
                    },
                },
            }
        )
    }


def _triggers() -> EntitiesConfig:
    return EntitiesConfig.model_validate(
        {
            "entities": [
                {
                    "id": "price",
                    "type": "trigger",
                    "attributes": {
                        "name": "price",
                        "wait_for": "event:price-drop",
                        "target": "dag:default",
                    },
                },
                {
                    "id": "morning",
                    "type": "trigger",
                    "attributes": {
                        "name": "morning",
                        "wait_for": 'cron:"0 9 * * *" AND event:market-open',
                        "target": "dag:morning",
                    },
                },
            ]
        }
    )
