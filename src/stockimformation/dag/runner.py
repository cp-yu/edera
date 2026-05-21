from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from stockimformation.dag.conditions import evaluate_condition
from stockimformation.dag.loader import load_graph, topological_layers
from stockimformation.dag.models import DagGraph, DagRunResult
from stockimformation.errors import DagError
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeContext, NodeInput, NodeOutput
from stockimformation.config.schema import DagConfig, DagNodeInstance, NodeConfig

NodeRunRecorder = Callable[[str, str, str | None], Awaitable[None]]


class DagRunner:
    def __init__(
        self,
        executor: NodeExecutor,
        recorder: NodeRunRecorder | None = None,
        dags: dict[str, DagConfig] | None = None,
        nodes: dict[str, NodeConfig] | None = None,
        depth: int = 1,
        path: tuple[str, ...] = (),
    ) -> None:
        self.executor = executor
        self.recorder = recorder
        self.dags = dags or {}
        self.nodes = nodes or executor.nodes
        self.depth = depth
        self.path = path

    async def run(self, graph: DagGraph, cycle_id: str, initial_payload: object) -> DagRunResult:
        if not self.executor.instances:
            self.executor.instances = graph.instances
        outputs: dict[str, NodeOutput] = {}
        failures: dict[str, str] = {}
        payloads: dict[str, object] = {}
        routed_edges: set[tuple[str, str]] = set()
        warnings: list[str] = []
        stream_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]] = {}
        layers = topological_layers(graph)
        for layer in layers:
            pending = [
                asyncio.create_task(
                    self._run_node(graph, node, cycle_id, initial_payload, outputs, payloads, routed_edges, warnings)
                )
                for node in layer
                if self._should_run(graph, node, routed_edges) and node not in stream_tasks
            ]
            while pending:
                done, pending_set = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                pending = list(pending_set)
                for task in done:
                    node, output = task.result()
                    self._store_result(graph, node, output, outputs, payloads, failures, routed_edges, warnings)
                    self._start_stream_tasks(
                        graph,
                        node,
                        cycle_id,
                        output,
                        outputs,
                        warnings,
                        stream_tasks,
                    )
            for node in layer:
                if node not in stream_tasks:
                    continue
                results = await asyncio.gather(*stream_tasks.pop(node))
                output = _merge_stream_results(node, [item for _name, item in results])
                self._store_result(graph, node, output, outputs, payloads, failures, routed_edges, warnings)
            if (
                layer == layers[0]
                and all(node in outputs and not outputs[node].ok for node in layer)
                and not any(graph.instances[node].type in self.dags for node in layer)
            ):
                raise DagError("all source nodes failed")
        return DagRunResult(
            cycle_id=cycle_id,
            node_outputs=outputs,
            failures=failures,
            payload=self._last_payload(graph, payloads),
            warnings=warnings,
        )

    def _store_result(
        self,
        graph: DagGraph,
        node: str,
        output: NodeOutput,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        failures: dict[str, str],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
    ) -> None:
        outputs[node] = output
        if output.ok:
            payloads[node] = output.payload
            routed_edges.update(self._routed_edges(graph, node, output.payload, warnings))
            return
        failures[node] = output.error or "node failed"
        if graph.instances[node].optional:
            routed_edges.update((node, downstream) for downstream in graph.edges[node])

    def _start_stream_tasks(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        output: NodeOutput,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
        stream_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]],
    ) -> None:
        if not output.ok:
            return
        for downstream in graph.edges[node]:
            if graph.fan_in_modes.get((node, downstream)) != "stream":
                continue
            stream_tasks.setdefault(downstream, []).append(
                asyncio.create_task(
                    self._run_stream_node(graph, downstream, cycle_id, output.payload, outputs, warnings)
                )
            )

    async def _run_stream_node(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        payload: object,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> tuple[str, NodeOutput]:
        node_input = NodeInput(cycle_id=cycle_id, payload=payload, metadata=self._metadata(graph, node, outputs, warnings))
        context = NodeContext(cycle_id, f"{node}:stream", graph.instances[node].type, graph.name)
        return node, await self._execute_node(graph.instances[node], node, node_input, context)

    async def _run_node(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
    ) -> tuple[str, NodeOutput]:
        input_payload = self._input_payload(graph, node, initial_payload, outputs, payloads, routed_edges)
        node_input = NodeInput(
            cycle_id=cycle_id,
            payload=input_payload,
            metadata=self._metadata(graph, node, outputs, warnings),
        )
        context = NodeContext(
            cycle_id=cycle_id,
            instance_id=node,
            node_type=graph.instances[node].type,
            dag_name=graph.name,
        )
        await self._record(node, "running")
        output = await self._execute_node(graph.instances[node], node, node_input, context)
        await self._record(node, "succeeded" if output.ok else "failed", output.error)
        return node, output

    async def _execute_node(
        self,
        instance: DagNodeInstance,
        node: str,
        node_input: NodeInput,
        context: NodeContext,
    ) -> NodeOutput:
        if instance.loop is None:
            if instance.type in self.dags:
                return await self._execute_sub_dag(instance, node_input)
            output = await self.executor.execute(node, node_input, context)
            return await self._fallback(instance, node_input, context, output)
        if instance.loop.mode == "parallel":
            return await self._execute_parallel_loop(instance, node, node_input, context)
        return await self._execute_serial_loop(instance, node, node_input, context)

    async def _fallback(
        self,
        instance: DagNodeInstance,
        node_input: NodeInput,
        context: NodeContext,
        output: NodeOutput,
    ) -> NodeOutput:
        if output.ok:
            return output
        if instance.fallback == "skip":
            return output.model_copy(update={"ok": True, "payload": None, "metadata": {"skipped": True}, "error": None})
        if instance.fallback == "switch_model" and instance.fallback_model:
            current = self.executor.instances.get(instance.id)
            parameters = dict(instance.config.get("parameters", {})) if isinstance(instance.config.get("parameters"), dict) else {}
            parameters["model"] = instance.fallback_model
            retry = instance.model_copy(
                update={"config": {**instance.config, "model": instance.fallback_model, "parameters": parameters}}
            )
            self.executor.instances[instance.id] = retry
            try:
                return await self.executor.execute(instance.id, node_input, context)
            finally:
                if current is not None:
                    self.executor.instances[instance.id] = current
        return output

    async def _execute_parallel_loop(
        self,
        instance: DagNodeInstance,
        node: str,
        node_input: NodeInput,
        context: NodeContext,
    ) -> NodeOutput:
        count = instance.loop.count if instance.loop and instance.loop.count is not None else 1
        results = await asyncio.gather(
            *[
                self.executor.execute(
                    node,
                    node_input,
                    NodeContext(context.cycle_id, f"{node}:{index}", context.node_type, context.dag_name),
                )
                for index in range(count)
            ]
        )
        payload = [result.payload for result in results if result.ok]
        failures = {f"{node}:{index}": result.error or "node failed" for index, result in enumerate(results) if not result.ok}
        matched = instance.loop.until is not None and any(
            result.ok and evaluate_condition(instance.loop.until or "", result.payload, self.executor.entity_store)
            for result in results
        )
        return NodeOutput(
            node_name=node,
            ok=bool(payload),
            payload=payload,
            metadata={"loop_failures": failures, "loop_until_matched": matched},
            error=None if payload else "; ".join(failures.values()) or "loop produced no output",
        )

    async def _execute_serial_loop(
        self,
        instance: DagNodeInstance,
        node: str,
        node_input: NodeInput,
        context: NodeContext,
    ) -> NodeOutput:
        count = instance.loop.count if instance.loop and instance.loop.count is not None else 1
        current_input = node_input
        last: NodeOutput | None = None
        for index in range(count):
            last = await self.executor.execute(
                node,
                current_input,
                NodeContext(context.cycle_id, f"{node}:{index}", context.node_type, context.dag_name),
            )
            if not last.ok:
                return last
            if instance.loop.until and evaluate_condition(instance.loop.until, last.payload, self.executor.entity_store):
                break
            current_input = NodeInput(
                cycle_id=node_input.cycle_id,
                payload=last.payload,
                metadata=node_input.metadata,
            )
        return last or NodeOutput(node_name=node, ok=False, error="loop produced no output")

    async def _execute_sub_dag(
        self,
        instance: DagNodeInstance,
        node_input: NodeInput,
    ) -> NodeOutput:
        limit = self.executor.system.max_dag_depth
        chain = (*self.path, instance.type)
        if instance.type in self.path:
            return NodeOutput(node_name=instance.id, ok=False, error=f"sub DAG cycle: {' -> '.join(chain)}")
        if self.depth >= limit:
            return NodeOutput(node_name=instance.id, ok=False, error=f"max DAG depth exceeded: {' -> '.join(chain)}")
        graph = load_graph(self.dags[instance.type], self.nodes)
        runner = DagRunner(
            self.executor,
            self.recorder,
            self.dags,
            self.nodes,
            self.depth + 1,
            chain,
        )
        try:
            result = await runner.run(graph, node_input.cycle_id, node_input.payload)
        except DagError as exc:
            return NodeOutput(node_name=instance.id, ok=False, error=str(exc))
        if result.ok:
            return NodeOutput(
                node_name=instance.id,
                ok=True,
                payload=result.payload,
                metadata={"sub_dag_failures": result.failures, "warnings": result.warnings},
            )
        error = "; ".join(result.failures.values()) or "sub DAG failed"
        return NodeOutput(node_name=instance.id, ok=False, error=error)

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
        routed_edges: set[tuple[str, str]],
    ) -> object:
        upstreams = graph.reverse_edges[node]
        if not upstreams:
            return initial_payload
        values = [
            payloads[name]
            for name in upstreams
            if outputs.get(name)
            and (outputs[name].ok or graph.instances[name].optional)
            and (name, node) in routed_edges
            and outputs[name].payload is not None
        ]
        if not values:
            return []
        if len(values) == 1:
            return values[0]
        return collect(values)

    def _metadata(
        self,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> dict[str, object]:
        metadata: dict[str, object] = {"upstreams": graph.reverse_edges[node]}
        failures: dict[str, str] = {}
        recovery: dict[str, object] = {}
        for upstream in graph.reverse_edges[node]:
            output = outputs.get(upstream)
            if output is None:
                continue
            failures.update(output.metadata.get("failures", {}))
            recovery.update(output.metadata.get("source_recovery", {}))
        if failures:
            metadata["failures"] = failures
        if recovery:
            metadata["source_recovery"] = recovery
        if warnings:
            metadata["warnings"] = warnings
        return metadata

    def _should_run(
        self,
        graph: DagGraph,
        node: str,
        routed_edges: set[tuple[str, str]],
    ) -> bool:
        upstreams = graph.reverse_edges[node]
        return not upstreams or any((upstream, node) in routed_edges for upstream in upstreams)

    def _routed_edges(
        self,
        graph: DagGraph,
        node: str,
        payload: object,
        warnings: list[str],
    ) -> set[tuple[str, str]]:
        routed: set[tuple[str, str]] = set()
        conditioned = 0
        for downstream in graph.edges[node]:
            condition = graph.conditions.get((node, downstream))
            if condition is None:
                routed.add((node, downstream))
                continue
            conditioned += 1
            if evaluate_condition(condition, payload, self.executor.entity_store):
                routed.add((node, downstream))
        if conditioned and not routed:
            warnings.append(f"dead path after {node}")
        return routed

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


def _merge_stream_results(node: str, results: list[NodeOutput]) -> NodeOutput:
    payload = [result.payload for result in results if result.ok]
    failures = {f"{node}:stream:{index}": result.error or "node failed" for index, result in enumerate(results) if not result.ok}
    return NodeOutput(
        node_name=node,
        ok=bool(payload),
        payload=payload,
        metadata={"stream_failures": failures},
        error=None if payload else "; ".join(failures.values()) or "stream produced no output",
    )
