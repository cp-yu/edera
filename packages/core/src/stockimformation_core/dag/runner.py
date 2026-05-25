from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
import asyncio

from stockimformation_core.dag.conditions import evaluate_condition
from stockimformation_core.dag.loader import load_graph, topological_layers
from stockimformation_core.dag.models import DagGraph, DagRunResult
from stockimformation_core.dag.resources import ResourceSemaphore, get_semaphore
from stockimformation_core.errors import DagError
from stockimformation_core.node.executor import NodeExecutor
from stockimformation_core.node.models import NodeContext, NodeInput, NodeOutput
from stockimformation_core.config.schema import DagConfig, DagNodeInstance, NodeConfig

NodeRunRecorder = Callable[[str, str, str | None], Awaitable[None]]


@dataclass(frozen=True)
class _NodeDone:
    node: str
    output: NodeOutput


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

    async def run(
        self,
        graph: DagGraph,
        cycle_id: str,
        initial_payload: object,
        stop_event: asyncio.Event | None = None,
        retry_nodes: set[str] | None = None,
        prefilled_outputs: dict[str, NodeOutput] | None = None,
    ) -> DagRunResult:
        if not self.executor.instances:
            self.executor.instances = graph.instances
        topological_layers(graph)
        stop_event = stop_event or asyncio.Event()
        outputs: dict[str, NodeOutput] = {}
        failures: dict[str, str] = {}
        payloads: dict[str, object] = {}
        routed_edges: set[tuple[str, str]] = set()
        warnings: list[str] = []
        for node, output in (prefilled_outputs or {}).items():
            if node not in graph.instances:
                continue
            outputs[node] = output
            if output.ok and output.payload is not None:
                payloads[node] = output.payload
                routed_edges.update(self._routed_edges(graph, node, output.payload, warnings))
        queue: asyncio.Queue[_NodeDone] = asyncio.Queue()
        running: dict[str, asyncio.Task[tuple[str, NodeOutput]]] = {}
        accumulate_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]] = {}
        accumulated_edges: set[tuple[str, str]] = set()
        acquired: dict[str, ResourceSemaphore] = {}
        started: set[str] = set(outputs)
        allowed = retry_nodes or set(graph.nodes)
        for node in graph.nodes:
            if node in outputs:
                continue
            if node in allowed and not graph.reverse_edges[node]:
                if not self._acquire_resource(graph.instances[node], acquired):
                    continue
                self._start_node(running, graph, node, cycle_id, initial_payload, outputs, payloads, routed_edges, warnings)
                started.add(node)
        try:
            while self._can_continue(
                running,
                accumulate_tasks,
                graph,
                started,
                allowed,
                outputs,
                routed_edges,
                accumulated_edges,
            ):
                if stop_event.is_set() and not running:
                    break
                if not running:
                    self._start_ready_nodes(
                        running,
                        graph,
                        cycle_id,
                        initial_payload,
                        outputs,
                        payloads,
                        routed_edges,
                        warnings,
                        started,
                        allowed,
                        stop_event,
                        acquired,
                    )
                    if not running and not self._pending_accumulate_tasks(accumulate_tasks):
                        await self._wait_for_resource_release(
                            graph,
                            started,
                            allowed,
                            outputs,
                            routed_edges,
                            accumulated_edges,
                            stop_event,
                        )
                        continue
                wait_tasks = [*running.values(), *self._pending_accumulate_tasks(accumulate_tasks)]
                running_tasks = set(running.values())
                release_task: asyncio.Task[None] | None = None
                if self._has_blocked_startable(graph, started, allowed, outputs, routed_edges) or self._has_blocked_accumulate(
                    graph,
                    started,
                    allowed,
                    outputs,
                    routed_edges,
                    accumulated_edges,
                ):
                    release_task = asyncio.create_task(
                        self._wait_for_resource_release(
                            graph,
                            started,
                            allowed,
                            outputs,
                            routed_edges,
                            accumulated_edges,
                            stop_event,
                        )
                    )
                    wait_tasks.append(release_task)
                done, _pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
                if release_task is not None and release_task not in done:
                    release_task.cancel()
                    await asyncio.gather(release_task, return_exceptions=True)
                for task in done:
                    if task not in running_tasks:
                        continue
                    result = task.result()
                    if result is None:
                        continue
                    node, output = result
                    running.pop(node, None)
                    await queue.put(_NodeDone(node, output))
                completed_accumulate = await self._complete_accumulate_tasks(
                    graph,
                    outputs,
                    payloads,
                    failures,
                    routed_edges,
                    warnings,
                    accumulate_tasks,
                    started,
                    acquired,
                )
                while not queue.empty():
                    event = await queue.get()
                    self._store_result(
                        graph,
                        event.node,
                        event.output,
                        outputs,
                        payloads,
                        failures,
                        routed_edges,
                        warnings,
                        acquired,
                    )
                    if event.output.ok:
                        await self._run_accumulate_downstreams(
                            graph,
                            event.node,
                            cycle_id,
                            event.output,
                            outputs,
                            payloads,
                            failures,
                            routed_edges,
                            warnings,
                            accumulate_tasks,
                            accumulated_edges,
                            started,
                            allowed,
                            stop_event,
                            acquired,
                        )
                        completed_accumulate = True
                    self._start_ready_nodes(
                        running,
                        graph,
                        cycle_id,
                        initial_payload,
                        outputs,
                        payloads,
                        routed_edges,
                        warnings,
                        started,
                        allowed,
                        stop_event,
                        acquired,
                    )
                if completed_accumulate:
                    self._start_ready_nodes(
                        running,
                        graph,
                        cycle_id,
                        initial_payload,
                        outputs,
                        payloads,
                        routed_edges,
                        warnings,
                        started,
                        allowed,
                        stop_event,
                        acquired,
                    )
        except asyncio.CancelledError:
            for task in running.values():
                task.cancel()
            await asyncio.gather(*running.values(), return_exceptions=True)
            self._release_all(acquired)
            raise
        except Exception:
            for task in running.values():
                task.cancel()
            await asyncio.gather(*running.values(), return_exceptions=True)
            self._release_all(acquired)
            raise
        source_nodes = [node for node in graph.nodes if not graph.reverse_edges[node]]
        if (
            source_nodes
            and all(node in outputs and not outputs[node].ok for node in source_nodes)
            and not any(graph.instances[node].type in self.dags for node in source_nodes)
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
        acquired: dict[str, ResourceSemaphore],
    ) -> None:
        self._release_resource(node, acquired)
        outputs[node] = output
        if output.ok:
            payloads[node] = output.payload
            routed_edges.update(self._routed_edges(graph, node, output.payload, warnings))
            return
        failures[node] = output.error or "node failed"
        if graph.instances[node].optional:
            routed_edges.update((node, downstream) for downstream in graph.edges[node])

    def _start_node(
        self,
        running: dict[str, asyncio.Task[tuple[str, NodeOutput]]],
        graph: DagGraph,
        node: str,
        cycle_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
    ) -> None:
        fan_out_payloads = self._fan_out_payloads(graph, node, outputs, routed_edges)
        if fan_out_payloads is not None:
            running[node] = asyncio.create_task(
                self._run_fan_out_node(graph, node, cycle_id, fan_out_payloads, outputs, warnings)
            )
            return
        running[node] = asyncio.create_task(
            self._run_node(graph, node, cycle_id, initial_payload, outputs, payloads, routed_edges, warnings)
        )

    def _start_ready_nodes(
        self,
        running: dict[str, asyncio.Task[tuple[str, NodeOutput]]],
        graph: DagGraph,
        cycle_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        started: set[str],
        allowed: set[str],
        stop_event: asyncio.Event,
        acquired: dict[str, ResourceSemaphore],
    ) -> None:
        if stop_event.is_set():
            return
        for node in graph.nodes:
            if node in started or node not in allowed or node in running:
                continue
            if self._node_fan_in_mode(graph, node) == "accumulate":
                continue
            if self._ready(graph, node, outputs, routed_edges):
                if not self._acquire_resource(graph.instances[node], acquired):
                    continue
                self._start_node(running, graph, node, cycle_id, initial_payload, outputs, payloads, routed_edges, warnings)
                started.add(node)

    async def _run_accumulate_downstreams(
        self,
        graph: DagGraph,
        upstream: str,
        cycle_id: str,
        output: NodeOutput,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        failures: dict[str, str],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        accumulate_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]],
        accumulated_edges: set[tuple[str, str]],
        started: set[str],
        allowed: set[str],
        stop_event: asyncio.Event,
        acquired: dict[str, ResourceSemaphore],
    ) -> None:
        if stop_event.is_set():
            return
        for downstream in graph.nodes:
            if downstream in outputs or downstream not in allowed:
                continue
            if self._node_fan_in_mode(graph, downstream) != "accumulate":
                continue
            for upstream_node in graph.reverse_edges[downstream]:
                edge = (upstream_node, downstream)
                if upstream_node not in outputs or edge not in routed_edges or edge in accumulated_edges:
                    continue
                resource_key = f"{downstream}:stream:{upstream_node}"
                if not self._acquire_resource(graph.instances[downstream], acquired, resource_key):
                    continue
                accumulated_edges.add(edge)
                accumulate_tasks.setdefault(downstream, []).append(
                    asyncio.create_task(
                        self._run_stream_node_releasing(
                            graph,
                            downstream,
                            cycle_id,
                            outputs[upstream_node].payload,
                            outputs,
                            warnings,
                            resource_key,
                            acquired,
                        )
                    )
                )
        await self._complete_accumulate_tasks(
            graph,
            outputs,
            payloads,
            failures,
            routed_edges,
            warnings,
            accumulate_tasks,
            started,
            acquired,
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

    async def _run_stream_node_releasing(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        payload: object,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
        resource_key: str,
        acquired: dict[str, ResourceSemaphore],
    ) -> tuple[str, NodeOutput]:
        try:
            return await self._run_stream_node(graph, node, cycle_id, payload, outputs, warnings)
        finally:
            self._release_resource(resource_key, acquired)

    async def _run_fan_out_node(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        payloads: list[object],
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> tuple[str, NodeOutput]:
        await self._record(node, "running")
        results = await asyncio.gather(
            *[
                self._run_fan_out_item(graph, node, cycle_id, payload, index, outputs, warnings)
                for index, payload in enumerate(payloads)
            ]
        )
        output = _merge_fan_out_results(node, results)
        await self._record(node, "succeeded" if output.ok else "failed", output.error)
        return node, output

    async def _run_fan_out_item(
        self,
        graph: DagGraph,
        node: str,
        cycle_id: str,
        payload: object,
        index: int,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> NodeOutput:
        node_input = NodeInput(cycle_id=cycle_id, payload=payload, metadata=self._metadata(graph, node, outputs, warnings))
        context = NodeContext(cycle_id, f"{node}:fanout:{index}", graph.instances[node].type, graph.name)
        return await self._execute_node(graph.instances[node], node, node_input, context)

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

    def _fan_out_payloads(
        self,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> list[object] | None:
        values: list[object] = []
        has_fan_out = False
        for upstream in graph.reverse_edges[node]:
            if (upstream, node) not in graph.fan_out_edges or (upstream, node) not in routed_edges:
                continue
            output = outputs.get(upstream)
            if output is None or not output.ok:
                continue
            has_fan_out = True
            if isinstance(output.payload, list):
                values.extend(output.payload)
            elif output.payload is not None:
                values.append(output.payload)
        return values if has_fan_out else None

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

    def _ready(
        self,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> bool:
        upstreams = graph.reverse_edges[node]
        if not upstreams:
            return True
        if not all(upstream in outputs for upstream in upstreams):
            return False
        return any((upstream, node) in routed_edges for upstream in upstreams)

    def _has_startable(
        self,
        graph: DagGraph,
        started: set[str],
        allowed: set[str],
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> bool:
        return any(
            node not in started
            and node in allowed
            and self._node_fan_in_mode(graph, node) != "accumulate"
            and self._ready(graph, node, outputs, routed_edges)
            and self._resource_available(graph.instances[node])
            for node in graph.nodes
        )

    def _has_blocked_startable(
        self,
        graph: DagGraph,
        started: set[str],
        allowed: set[str],
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> bool:
        return any(
            node not in started
            and node in allowed
            and self._node_fan_in_mode(graph, node) != "accumulate"
            and self._ready(graph, node, outputs, routed_edges)
            and not self._resource_available(graph.instances[node])
            for node in graph.nodes
        )

    def _has_blocked_accumulate(
        self,
        graph: DagGraph,
        started: set[str],
        allowed: set[str],
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
        accumulated_edges: set[tuple[str, str]],
    ) -> bool:
        return any(
            node not in started
            and node in allowed
            and self._node_fan_in_mode(graph, node) == "accumulate"
            and graph.instances[node].resource is not None
            and upstream in outputs
            and (upstream, node) in routed_edges
            and (upstream, node) not in accumulated_edges
            and not self._resource_available(graph.instances[node])
            for node in graph.nodes
            for upstream in graph.reverse_edges[node]
        )

    def _can_continue(
        self,
        running: dict[str, asyncio.Task[tuple[str, NodeOutput]]],
        accumulate_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]],
        graph: DagGraph,
        started: set[str],
        allowed: set[str],
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
        accumulated_edges: set[tuple[str, str]],
    ) -> bool:
        return bool(running) or bool(self._pending_accumulate_tasks(accumulate_tasks)) or self._has_startable(
            graph,
            started,
            allowed,
            outputs,
            routed_edges,
        ) or self._has_blocked_startable(
            graph,
            started,
            allowed,
            outputs,
            routed_edges,
        ) or self._has_blocked_accumulate(
            graph,
            started,
            allowed,
            outputs,
            routed_edges,
            accumulated_edges,
        )

    def _pending_accumulate_tasks(
        self,
        accumulate_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]],
    ) -> list[asyncio.Task[tuple[str, NodeOutput]]]:
        return [task for tasks in accumulate_tasks.values() for task in tasks if not task.done()]

    async def _complete_accumulate_tasks(
        self,
        graph: DagGraph,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        failures: dict[str, str],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        accumulate_tasks: dict[str, list[asyncio.Task[tuple[str, NodeOutput]]]],
        started: set[str],
        acquired: dict[str, ResourceSemaphore],
    ) -> bool:
        completed = False
        for node in list(accumulate_tasks):
            if node in outputs:
                accumulate_tasks.pop(node, None)
                continue
            if not all(name in outputs for name in graph.reverse_edges[node]):
                continue
            tasks = accumulate_tasks.get(node, [])
            if not tasks or any(not task.done() for task in tasks):
                continue
            accumulate_tasks.pop(node, None)
            results = await asyncio.gather(*tasks)
            merged = _merge_stream_results(node, [item for _name, item in results])
            self._store_result(
                graph,
                node,
                merged,
                outputs,
                payloads,
                failures,
                routed_edges,
                warnings,
                acquired,
            )
            started.add(node)
            completed = True
        return completed

    async def _wait_for_resource_release(
        self,
        graph: DagGraph,
        started: set[str],
        allowed: set[str],
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
        accumulated_edges: set[tuple[str, str]],
        stop_event: asyncio.Event,
    ) -> None:
        blocked = [
            get_semaphore(graph.instances[node].resource, self.executor.entity_store)
            for node in graph.nodes
            if node not in started
            and node in allowed
            and graph.instances[node].resource is not None
            and self._node_fan_in_mode(graph, node) != "accumulate"
            and self._ready(graph, node, outputs, routed_edges)
        ]
        blocked.extend(
            get_semaphore(graph.instances[node].resource, self.executor.entity_store)
            for node in graph.nodes
            for upstream in graph.reverse_edges[node]
            if node not in started
            and node in allowed
            and graph.instances[node].resource is not None
            and self._node_fan_in_mode(graph, node) == "accumulate"
            and upstream in outputs
            and (upstream, node) in routed_edges
            and (upstream, node) not in accumulated_edges
        )
        if not blocked:
            return
        wait_tasks = [asyncio.create_task(item.released.wait()) for item in blocked]
        wait_tasks.append(asyncio.create_task(stop_event.wait()))
        done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for item in blocked:
            item.released.clear()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()

    def _acquire_resource(
        self,
        instance: DagNodeInstance,
        acquired: dict[str, ResourceSemaphore],
        key: str | None = None,
    ) -> bool:
        if instance.resource is None:
            return True
        resource = get_semaphore(instance.resource, self.executor.entity_store)
        if not resource.acquire_nowait():
            return False
        acquired[key or instance.id] = resource
        return True

    def _resource_available(self, instance: DagNodeInstance) -> bool:
        if instance.resource is None:
            return True
        return get_semaphore(instance.resource, self.executor.entity_store).available()

    def _release_resource(self, node: str, acquired: dict[str, ResourceSemaphore]) -> None:
        resource = acquired.pop(node, None)
        if resource is not None:
            resource.release()

    def _release_all(self, acquired: dict[str, ResourceSemaphore]) -> None:
        for node in list(acquired):
            self._release_resource(node, acquired)

    def _node_fan_in_mode(self, graph: DagGraph, node: str) -> str:
        mode = graph.instances[node].fan_in_mode
        if mode != "barrier":
            return mode
        if any(graph.fan_in_modes.get((upstream, node)) in {"stream", "accumulate"} for upstream in graph.reverse_edges[node]):
            return "accumulate"
        return "barrier"

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


def _merge_fan_out_results(node: str, results: list[NodeOutput]) -> NodeOutput:
    payload = [result.payload for result in results if result.ok]
    failures = {f"{node}:fanout:{index}": result.error or "node failed" for index, result in enumerate(results) if not result.ok}
    return NodeOutput(
        node_name=node,
        ok=bool(payload),
        payload=payload,
        metadata={"fan_out_failures": failures},
        error=None if payload else "; ".join(failures.values()) or "fan_out produced no output",
    )
