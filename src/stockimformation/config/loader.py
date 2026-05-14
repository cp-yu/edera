from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import yaml

from stockimformation.config.schema import (
    AppConfig,
    DagConfig,
    NodeConfig,
    PortfolioConfig,
    RuntimeSettings,
    SystemConfig,
)
from stockimformation.errors import ConfigError


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a mapping: {path}")
    return data


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    return tomllib.loads(path.read_text())


def load_system_config(path: Path) -> SystemConfig:
    return SystemConfig.model_validate(_read_toml(path))


def load_portfolio_config(path: Path) -> PortfolioConfig:
    return PortfolioConfig.model_validate(_read_yaml(path))


def load_node_configs(path: Path) -> dict[str, NodeConfig]:
    configs: dict[str, NodeConfig] = {}
    for file in sorted(path.glob("*.yaml")):
        node = NodeConfig.model_validate(_read_yaml(file))
        configs[node.name] = node
    return configs


def load_dag_configs(path: Path) -> dict[str, DagConfig]:
    configs: dict[str, DagConfig] = {}
    for file in sorted(path.glob("*.yaml")):
        dag = DagConfig.model_validate(_read_yaml(file))
        configs[dag.name] = dag
    return configs


def load_app_config(config_dir: Path = Path("config")) -> AppConfig:
    return AppConfig(
        system=load_system_config(config_dir / "system.toml"),
        portfolio=load_portfolio_config(config_dir / "portfolio.yaml"),
        runtime=RuntimeSettings(),
        nodes=load_node_configs(config_dir / "nodes"),
        dags=load_dag_configs(config_dir / "dags"),
    )
