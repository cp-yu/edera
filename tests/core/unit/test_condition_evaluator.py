from pathlib import Path

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.dag.conditions import evaluate_condition


def test_default_condition_evaluator() -> None:
    assert evaluate_condition(
        "output.sentiment == 'negative' and output.confidence > 0.7",
        {"sentiment": "negative", "confidence": 0.9},
    )
    assert evaluate_condition("output.category in ['tech', 'finance']", {"category": "tech"})


def test_condition_evaluator_entity_ref() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
            }
        )
    }
    entities = EntitiesConfig.model_validate(
        {"entities": [{"id": "stock-1", "type": "stock", "attributes": {"code": "00700", "threshold": 100}}]}
    )
    store = EntityStore(entities, entity_types, EntityRelationsConfig())

    assert evaluate_condition("output.price > entity:stock:00700.threshold", {"price": 120}, store)


def test_custom_condition_evaluator(tmp_path: Path) -> None:
    evaluators = tmp_path / "evaluators"
    evaluators.mkdir()
    evaluators.joinpath("custom.py").write_text(
        "def evaluate(expression, context):\n"
        "    return expression == 'custom' and context['output']['ok']\n",
        encoding="utf-8",
    )

    assert evaluate_condition("custom", {"ok": True}, evaluators_dir=evaluators)
