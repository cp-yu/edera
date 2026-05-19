from __future__ import annotations

from pathlib import Path

import yaml


def migrate(config_dir: Path = Path("config")) -> None:
    portfolio_path = config_dir / "portfolio.yaml"
    if not portfolio_path.exists():
        return
    portfolio = yaml.safe_load(portfolio_path.read_text(encoding="utf-8")) or {}
    targets = portfolio.get("targets", [])
    sources = portfolio.get("sources", [])
    entities: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []
    for target in targets:
        code = str(target["code"])
        entity = {
            "id": f"stock-{_slug(code)}",
            "type": "stock",
            "attributes": {
                "code": code,
                "name": target["name"],
            },
        }
        if target.get("holding") is not None:
            entity["attributes"]["holding"] = target["holding"]
        entities.append(entity)
        for source_name in target.get("sources", []):
            source_type = _source_entity_type(sources, str(source_name))
            relations.append({"entities": [f"stock:{code}", f"{source_type}:{source_name}"], "type": "uses-source"})
    for source in sources:
        source_type = "rss-source" if source["type"] == "rss" else "web-source"
        attributes = {"name": source["name"], "url": str(source["url"])}
        for key in ("selector", "regex"):
            if source.get(key):
                attributes[key] = source[key]
        entities.append({"id": f"source-{_slug(source['name'])}", "type": source_type, "attributes": attributes})
    (config_dir / "entities.yaml").write_text(
        yaml.safe_dump({"entities": entities}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text(
        yaml.safe_dump({"relations": relations}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _source_entity_type(sources: list[dict[str, object]], name: str) -> str:
    for source in sources:
        if source.get("name") == name:
            return "rss-source" if source.get("type") == "rss" else "web-source"
    return "web-source"


def _slug(value: object) -> str:
    return str(value).lower().replace(".", "-").replace("_", "-")


if __name__ == "__main__":
    migrate()
