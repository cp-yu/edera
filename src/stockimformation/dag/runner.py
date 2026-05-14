from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from stockimformation.dag.loader import topological_layers
from stockimformation.dag.models import DagGraph, DagRunResult
from stockimformation.errors import DagError
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeContext, NodeInput, NodeOutput

NodeRunRecorder = Callable[[str, str, str | None], Awaitable[None]]


class DagRunner:
    def __init__(self, executor: NodeExecutor, recorder: NodeRunRecorder | None = None) -> None:
        self.executor = executor
        self.recorder = recorder

    async def run(self, graph: DagGraph, cycle_id: str, initial_payload: object) -> DagRunResult:
        outputs: dict[str, NodeOutput] = {}
        failures: dict[str, str] = {}
        payloads: dict[str, object] = {}
        layers = topological_layers(graph)
        for layer in layers:
            tasks = [
                self._run_node(graph, node, cycle_id, initial_payload, outputs, payloads)
                for node in layer
            ]
            results = await asyncio.gather(*tasks)
            for node, output in results:
                outputs[node] = output
                if output.ok:
                    payloads[node] = output.payload
                else:
                    failures[node] = output.error or "node failed"
            if layer == layers[0] and all(not outputs[node].ok for node in layer):
                raise DagError("all source nodes failed")
        return DagRunResult(
            cycle_id=cycle_id,
            node_outputs=outputs,
            failures=failures,
            payload=self._last_payload(graph, payloads),
        )

    async def _run_node(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
    ) -> tuple[str, NodeOutput]:
        input_payload = self._input_payload(graph, node, initial_payload, outputs, payloads)
        node_input = NodeInput(
            cycle_id=cycle_id,
            payload=input_payload,
            metadata={"upstreams": graph.reverse_edges[node]},
        )
        context = NodeContext(cycle_id=cycle_id, instance_id=node)
        await self._record(node, "running")
        output = await self.executor.execute(node, node_input, context)
        await self._record(node, "succeeded" if output.ok else "failed", output.error)
        return node, output

    async def _record(self, node: str, status: str, error: str | None = None) -> None:
        if self.recorder is not None:
            await self.recorder(node, status, error)

    def _input_payload(
        self,
        graph: DagGraph,
        node: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
    ) -> object:
        upstreams = graph.reverse_edges[node]
        if not upstreams:
            return initial_payload
        values = [payloads[name] for name in upstreams if outputs.get(name) and outputs[name].ok]
        if not values:
            return []
        if len(values) == 1:
            return values[0]
        return collect(values)

    def _last_payload(self, graph: DagGraph, payloads: dict[str, object]) -> object:
        sinks = [node for node in graph.nodes if not graph.edges[node]]
        if not sinks:
            return None
        if len(sinks) == 1:
            return payloads.get(sinks[0])
        return [payloads.get(node) for node in sinks]


def collect(values: Sequence[object]) -> list[object]:
    collected: list[object] = []
    for value in values:
        if isinstance(value, list):
            collected.extend(value)
        else:
            collected.append(value)
    return collected
