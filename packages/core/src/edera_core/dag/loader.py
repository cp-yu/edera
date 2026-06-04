from edera_core.config.schema import DagConfig, DagEdge, NodeConfig
from edera_core.dag.models import DagGraph
from edera_core.errors import DagError


def load_graph(config: DagConfig, nodes: dict[str, NodeConfig], dags: dict[str, DagConfig] | None = None) -> DagGraph:
    instances = {node.id: node for node in config.nodes}
    if len(instances) != len(config.nodes):
        raise DagError("DAG contains duplicate node instance ids")
    sub_dag_instances = {node.id for node in config.nodes if _is_sub_dag_node(node, dags)}
    missing = [node.type for node in config.nodes if node.id not in sub_dag_instances and node.type not in nodes]
    if missing:
        raise DagError(f"missing node config: {', '.join(missing)}")
    instance_ids = [node.id for node in config.nodes]
    edges: dict[str, list[str]] = {node_id: [] for node_id in instance_ids}
    reverse: dict[str, list[str]] = {node_id: [] for node_id in instance_ids}
    fan_out: set[tuple[str, str]] = set()
    fan_in: set[tuple[str, str]] = set()
    optional: set[tuple[str, str]] = set()
    conditions: dict[tuple[str, str], str] = {}
    fan_in_modes: dict[tuple[str, str], str] = {}
    for raw_edge in config.edges:
        edge = raw_edge if isinstance(raw_edge, DagEdge) else DagEdge.model_validate(raw_edge)
        if edge.from_ not in edges or edge.to not in reverse:
            raise DagError(f"edge references unknown node: {edge.from_}->{edge.to}")
        if edge.from_ not in sub_dag_instances and edge.to not in sub_dag_instances:
            _check_role(nodes[instances[edge.from_].type], nodes[instances[edge.to].type])
            _check_io(nodes[instances[edge.from_].type], nodes[instances[edge.to].type])
        edges[edge.from_].append(edge.to)
        reverse[edge.to].append(edge.from_)
        if edge.fan_out:
            fan_out.add((edge.from_, edge.to))
        if edge.fan_in:
            fan_in.add((edge.from_, edge.to))
        upstream = instances[edge.from_]
        upstream_node_optional = False if edge.from_ in sub_dag_instances else nodes[upstream.type].optional
        if edge.optional or upstream_node_optional or upstream.optional:
            optional.add((edge.from_, edge.to))
        if edge.condition:
            conditions[(edge.from_, edge.to)] = edge.condition
        fan_in_modes[(edge.from_, edge.to)] = edge.fan_in_mode
    _assert_acyclic(instance_ids, edges)
    return DagGraph(config.name, instance_ids, instances, edges, reverse, fan_out, fan_in, optional, conditions, fan_in_modes)


def topological_layers(graph: DagGraph) -> list[list[str]]:
    incoming = {name: len(graph.reverse_edges[name]) for name in graph.nodes}
    ready = sorted(name for name, count in incoming.items() if count == 0)
    layers: list[list[str]] = []
    visited = 0
    while ready:
        layer = ready
        layers.append(layer)
        ready = []
        for node in layer:
            visited += 1
            for downstream in graph.edges[node]:
                incoming[downstream] -= 1
                if incoming[downstream] == 0:
                    ready.append(downstream)
        ready.sort()
    if visited != len(graph.nodes):
        raise DagError("DAG contains a cycle")
    return layers


def validate_sub_dag_nesting(
    dags: dict[str, DagConfig],
    max_depth: int,
) -> None:
    for dag_name in dags:
        _visit_sub_dag(dags, dag_name, max_depth, ())


def _check_io(upstream: NodeConfig, downstream: NodeConfig) -> None:
    if upstream.output_type == "Any" or downstream.input_type == "Any":
        return
    if upstream.output_type == downstream.input_type:
        return
    raise DagError(f"I/O type mismatch: {upstream.name}->{downstream.name}")


def _check_role(upstream: NodeConfig, downstream: NodeConfig) -> None:
    if upstream.role == "sink":
        raise DagError(f"sink node cannot have outgoing edge: {upstream.name}")
    if downstream.role == "source":
        raise DagError(f"source node cannot have incoming edge: {downstream.name}")


def _assert_acyclic(nodes: list[str], edges: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise DagError(f"DAG contains a cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for downstream in edges[node]:
            visit(downstream)
        visiting.remove(node)
        visited.add(node)

    for node in nodes:
        visit(node)


def _visit_sub_dag(
    dags: dict[str, DagConfig],
    dag_name: str,
    max_depth: int,
    path: tuple[str, ...],
) -> None:
    chain = (*path, dag_name)
    if dag_name in path:
        raise DagError(f"sub DAG cycle: {' -> '.join(chain)}")
    if len(chain) > max_depth:
        raise DagError(f"max DAG depth exceeded: {' -> '.join(chain)}")
    dag = dags[dag_name]
    for node in dag.nodes:
        ref = _dag_ref(dags, node.type, node.dag_ref)
        if ref is not None:
            _visit_sub_dag(dags, ref, max_depth, chain)


def _dag_ref(dags: dict[str, DagConfig], node_type: str, dag_ref: str | None = None) -> str | None:
    if node_type == "dag" and dag_ref in dags:
        return dag_ref
    if node_type in dags:
        return node_type
    return None


def _is_sub_dag_node(node, dags: dict[str, DagConfig] | None) -> bool:
    if node.type == "dag" and node.dag_ref:
        return dags is None or node.dag_ref in dags
    return dags is not None and node.type in dags
