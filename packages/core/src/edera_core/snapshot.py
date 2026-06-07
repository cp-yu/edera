from __future__ import annotations

from dataclasses import dataclass

from edera_core.config.schema import DagConfig, EntityTypeConfig, NodeConfig, SkillConfig
from edera_core.errors import DagError
from edera_core.resolver import DatabaseHandlerResolver


@dataclass(frozen=True)
class _DagPathStep:
    dag_name: str
    via_node_id: str | None = None


@dataclass(frozen=True)
class DagExecutionClosure:
    root_dag_name: str
    dags: dict[str, DagConfig]
    node_configs: dict[str, NodeConfig]


@dataclass(frozen=True)
class DagExecutionSnapshot:
    dag_closure: DagExecutionClosure
    entity_types: dict[str, EntityTypeConfig]
    handler_resolver: DatabaseHandlerResolver
    extension_table_names: dict[str, dict[str, str]]
    skills: dict[str, SkillConfig]

    @classmethod
    async def create(
        cls,
        dag_config: DagConfig,
        node_configs: dict[str, NodeConfig],
        entity_types: dict[str, EntityTypeConfig],
        session,
        handlers_dir,
        extension_table_names: dict[str, dict[str, str]] | None = None,
        skills: dict[str, SkillConfig] | None = None,
    ) -> DagExecutionSnapshot:
        dag_closure = build_dag_execution_closure(dag_config.name, {dag_config.name: dag_config}, node_configs)
        return cls(
            dag_closure,
            dict(entity_types),
            await DatabaseHandlerResolver.snapshot(session, handlers_dir),
            {key: dict(value) for key, value in (extension_table_names or {}).items()},
            _closure_skills(dag_closure, skills or {}),
        )

    @classmethod
    async def from_closure(
        cls,
        dag_closure: DagExecutionClosure,
        entity_types: dict[str, EntityTypeConfig],
        session,
        handlers_dir,
        extension_table_names: dict[str, dict[str, str]] | None = None,
        skills: dict[str, SkillConfig] | None = None,
    ) -> DagExecutionSnapshot:
        return cls(
            dag_closure,
            dict(entity_types),
            await DatabaseHandlerResolver.snapshot(session, handlers_dir),
            {key: dict(value) for key, value in (extension_table_names or {}).items()},
            _closure_skills(dag_closure, skills or {}),
        )

    @property
    def dag_config(self) -> DagConfig:
        return self.dag_closure.dags[self.dag_closure.root_dag_name]

    @property
    def node_configs(self) -> dict[str, NodeConfig]:
        return self.dag_closure.node_configs


def build_dag_execution_closure(
    root_dag_name: str,
    dags: dict[str, DagConfig],
    nodes: dict[str, NodeConfig],
) -> DagExecutionClosure:
    closure_dags: dict[str, DagConfig] = {}
    closure_nodes: dict[str, NodeConfig] = {}

    def visit(dag_name: str, path: tuple[_DagPathStep, ...], via_node_id: str | None = None) -> None:
        dag = dags.get(dag_name)
        if dag is None:
            raise DagError(f"missing DAG config: {dag_name}")
        step = _DagPathStep(dag_name=dag_name, via_node_id=via_node_id)
        chain = (*path, step)
        if dag_name in {item.dag_name for item in path}:
            raise DagError(_format_cycle_error(chain, chain[0].dag_name))
        closure_dags[dag_name] = dag
        for instance in dag.nodes:
            sub_dag_name = _sub_dag_name(instance.type, instance.dag_ref, dags)
            if sub_dag_name is not None:
                visit(sub_dag_name, chain, instance.id)
                continue
            node = nodes.get(instance.type)
            if node is None:
                raise DagError(f"missing node config: {instance.type}")
            closure_nodes[instance.type] = node

    visit(root_dag_name, ())
    return DagExecutionClosure(root_dag_name, closure_dags, closure_nodes)


def _sub_dag_name(node_type: str, dag_ref: str | None, dags: dict[str, DagConfig]) -> str | None:
    if node_type == "dag" and dag_ref:
        return dag_ref
    if node_type in dags:
        return node_type
    return None


def _closure_skills(
    dag_closure: DagExecutionClosure,
    skills: dict[str, SkillConfig],
) -> dict[str, SkillConfig]:
    needed: set[str] = set()
    for node in dag_closure.node_configs.values():
        needed.update(getattr(node, "skills", []) or [])
    return {name: skills[name] for name in sorted(needed) if name in skills}


def _format_cycle_error(chain: tuple[_DagPathStep, ...], root_dag: str) -> str:
    names = " -> ".join(step.dag_name for step in chain)
    return f"Sub DAG cycle detected for '{root_dag}': {names}"
