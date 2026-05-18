from stockimformation.config.schema import DagConfig, DagEdge, NodeConfig
from stockimformation.dag.models import DagGraph
from stockimformation.errors import DagError


def load_graph(config: DagConfig, nodes: dict[str, NodeConfig]) -> DagGraph:
    instances = {node.id: node for node in config.nodes}
    if len(instances) != len(config.nodes):
        raise DagError("DAG contains duplicate node instance ids")
    missing = [node.type for node in config.nodes if node.type not in nodes]
    if missing:
        raise DagError(f"missing node config: {', '.join(missing)}")
    instance_ids = [node.id for node in config.nodes]
    edges: dict[str, list[str]] = {node_id: [] for node_id in instance_ids}
    reverse: dict[str, list[str]] = {node_id: [] for node_id in instance_ids}
    fan_out: set[tuple[str, str]] = set()
    fan_in: set[tuple[str, str]] = set()
    for raw_edge in config.edges:
        edge = raw_edge if isinstance(raw_edge, DagEdge) else DagEdge.model_validate(raw_edge)
        if edge.from_ not in edges or edge.to not in reverse:
            raise DagError(f"edge references unknown node: {edge.from_}->{edge.to}")
        _check_role(nodes[instances[edge.from_].type], nodes[instances[edge.to].type])
        _check_io(nodes[instances[edge.from_].type], nodes[instances[edge.to].type])
        edges[edge.from_].append(edge.to)
        reverse[edge.to].append(edge.from_)
        if edge.fan_out:
            fan_out.add((edge.from_, edge.to))
        if edge.fan_in:
            fan_in.add((edge.from_, edge.to))
    _assert_acyclic(instance_ids, edges)
    return DagGraph(config.name, instance_ids, instances, edges, reverse, fan_out, fan_in)


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


def _check_io(upstream: NodeConfig, downstream: NodeConfig) -> None:
    if upstream.output_type == "Any" or downstream.input_type == "Any":
        return
    if upstream.output_type == downstream.input_type:
        return
    if upstream.type == "llm" or downstream.type == "llm":
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
