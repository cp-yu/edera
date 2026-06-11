from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
import asyncio
import logging
from uuid import uuid4

from edera_core.dag.conditions import evaluate_condition
from edera_core.dag.loader import DagPathStep, _format_cycle_error, load_graph, topological_layers
from edera_core.dag.models import DagGraph, DagRunResult
from edera_core.dag.resources import ResourceSemaphore, get_semaphore
from edera_core.errors import DagError
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeContext, NodeInput, NodeOutput
from edera_core.config.schema import DagConfig, DagNodeInstance, DagNodeConfig, EmitDeclaration, NodeConfig
from edera_core.trigger import TriggerExecutor

NodeRunRecorder = Callable[[str, str, str, str | None, str | None, dict[str, object] | None], Awaitable[None]]
EdgeInputRecorder = Callable[["EdgeInputFact"], Awaitable[None]]
EmitCallback = Callable[[str, object | None], Awaitable[None]]
DagRunLifecycle = Callable[[str, str, str, str | None], Awaitable[None]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EdgeInputFact:
    run_id: str
    from_node_id: str
    to_node_id: str
    edge_optional: bool
    status: str
    has_payload: bool
    error_summary: str | None = None


@dataclass(frozen=True)
class _NodeDone:
    node: str
    output: NodeOutput


@dataclass(frozen=True)
class _RunInputs:
    source_shared_inputs: object | None
    node_inputs: dict[str, object]
    append_nodes: set[str]


class DagRunner:
    def __init__(
        self,
        executor: NodeExecutor,
        recorder: NodeRunRecorder | None = None,
        edge_recorder: EdgeInputRecorder | None = None,
        dags: dict[str, DagConfig] | None = None,
        nodes: dict[str, NodeConfig] | None = None,
        emit: EmitCallback | None = None,
        dag_lifecycle: DagRunLifecycle | None = None,
        trigger_executor: TriggerExecutor | None = None,
        depth: int = 1,
        path: tuple[DagPathStep, ...] = (),
    ) -> None:
        self.executor = executor
        self.recorder = recorder
        self.edge_recorder = edge_recorder
        self.dags = dags or {}
        self.nodes = nodes or executor.nodes
        self.emit = emit
        self.dag_lifecycle = dag_lifecycle
        self.trigger_executor = trigger_executor
        self.depth = depth
        self.path = path
        if self.executor.dag_executor is None:
            self.executor.dag_executor = self._execute_dag_node_config

    async def run(
        self,
        graph: DagGraph,
        run_id: str,
        initial_payload: object,
        stop_event: asyncio.Event | None = None,
        retry_nodes: set[str] | None = None,
        prefilled_outputs: dict[str, NodeOutput] | None = None,
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
    ) -> DagRunResult:
        previous_instances = self.executor.instances
        previous_path = self.path
        self.executor.instances = graph.instances
        if not self.path:
            self.path = (DagPathStep(dag_name=graph.name),)
        try:
            topological_layers(graph)
            stop_event = stop_event or asyncio.Event()
            self._configure_wait_executor(stop_event)
            outputs: dict[str, NodeOutput] = {}
            failures: dict[str, str] = {}
            payloads: dict[str, object] = {}
            run_inputs = _RunInputs(source_shared_inputs, dict(node_inputs or {}), set(append_nodes or set()))
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
                    instance = graph.instances[node]
                    if instance.loop is None and not self._acquire_resource(instance, acquired):
                        continue
                    self._start_node(
                        running,
                        graph,
                        node,
                        run_id,
                        initial_payload,
                        outputs,
                        payloads,
                        routed_edges,
                        warnings,
                        run_inputs,
                    )
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
                        await self._start_ready_nodes(
                            running,
                            graph,
                            run_id,
                            initial_payload,
                            outputs,
                            payloads,
                            failures,
                            routed_edges,
                            warnings,
                            run_inputs,
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
                            await self._emit_node_events(graph, event.node, event.output.payload)
                            await self._run_accumulate_downstreams(
                                graph,
                                event.node,
                                run_id,
                                event.output,
                                outputs,
                                payloads,
                                failures,
                                routed_edges,
                                warnings,
                                run_inputs,
                                accumulate_tasks,
                                accumulated_edges,
                                started,
                                allowed,
                                stop_event,
                                acquired,
                            )
                            completed_accumulate = True
                        await self._start_ready_nodes(
                            running,
                            graph,
                            run_id,
                            initial_payload,
                            outputs,
                            payloads,
                            failures,
                            routed_edges,
                            warnings,
                            run_inputs,
                            started,
                            allowed,
                            stop_event,
                            acquired,
                        )
                    if completed_accumulate:
                        await self._start_ready_nodes(
                            running,
                            graph,
                            run_id,
                            initial_payload,
                            outputs,
                            payloads,
                            failures,
                            routed_edges,
                            warnings,
                            run_inputs,
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
            source_nodes = [node for node in graph.nodes if node in allowed and not graph.reverse_edges[node]]
            if (
                source_nodes
                and not stop_event.is_set()
                and all(node in outputs and not outputs[node].ok for node in source_nodes)
                and not any(self._is_sub_dag_instance(graph.instances[node]) for node in source_nodes)
            ):
                raise DagError("all source nodes failed")
            return DagRunResult(
                run_id=run_id,
                node_outputs=outputs,
                failures=failures,
                payload=self._last_payload(graph, payloads),
                warnings=warnings,
            )
        finally:
            self.executor.instances = previous_instances
            self.path = previous_path

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
        routed_edges.update((node, downstream) for downstream in graph.edges[node] if (node, downstream) in graph.optional_edges)

    def _start_node(
        self,
        running: dict[str, asyncio.Task[tuple[str, NodeOutput]]],
        graph: DagGraph,
        node: str,
        run_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        run_inputs: _RunInputs,
    ) -> None:
        fan_out_payloads = self._fan_out_payloads(graph, node, outputs, routed_edges)
        if fan_out_payloads is not None:
            running[node] = asyncio.create_task(
                self._run_fan_out_node(graph, node, run_id, fan_out_payloads, outputs, warnings)
            )
            return
        running[node] = asyncio.create_task(
            self._run_node(graph, node, run_id, initial_payload, outputs, payloads, routed_edges, warnings, run_inputs)
        )

    async def _start_ready_nodes(
        self,
        running: dict[str, asyncio.Task[tuple[str, NodeOutput]]],
        graph: DagGraph,
        run_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        failures: dict[str, str],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        run_inputs: _RunInputs,
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
                instance = graph.instances[node]
                if instance.loop is None and not self._acquire_resource(instance, acquired):
                    continue
                await self._record_edge_inputs(run_id, graph, node, outputs, routed_edges)
                self._start_node(
                    running,
                    graph,
                    node,
                    run_id,
                    initial_payload,
                    outputs,
                    payloads,
                    routed_edges,
                    warnings,
                    run_inputs,
                )
                started.add(node)
            elif self._blocked_by_required_failure(graph, node, outputs, routed_edges):
                await self._record_edge_inputs(run_id, graph, node, outputs, routed_edges)
                error = self._upstream_failure_error(graph, node, outputs, routed_edges)
                await self._record(run_id, node, "failed", error, "upstream_failed")
                self._store_result(
                    graph,
                    node,
                    NodeOutput(node_name=node, ok=False, error=error),
                    outputs,
                    payloads,
                    failures,
                    routed_edges,
                    warnings,
                    acquired,
                )
                started.add(node)

    async def _run_accumulate_downstreams(
        self,
        graph: DagGraph,
        upstream: str,
        run_id: str,
        output: NodeOutput,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        failures: dict[str, str],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        run_inputs: _RunInputs,
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
                            run_id,
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
        run_id: str,
        payload: object,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> tuple[str, NodeOutput]:
        node_input = NodeInput(run_id=run_id, payload=payload, metadata=self._metadata(graph, node, outputs, warnings))
        context = NodeContext(run_id, f"{node}:stream", graph.instances[node].type, graph.name)
        return node, await self._execute_node(graph.instances[node], node, node_input, context)

    async def _run_stream_node_releasing(
        self,
        graph: DagGraph,
        node: str,
        run_id: str,
        payload: object,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
        resource_key: str,
        acquired: dict[str, ResourceSemaphore],
    ) -> tuple[str, NodeOutput]:
        try:
            return await self._run_stream_node(graph, node, run_id, payload, outputs, warnings)
        finally:
            self._release_resource(resource_key, acquired)

    async def _run_fan_out_node(
        self,
        graph: DagGraph,
        node: str,
        run_id: str,
        payloads: list[object],
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> tuple[str, NodeOutput]:
        await self._record(run_id, node, "running")
        results = await asyncio.gather(
            *[
                self._run_fan_out_item(graph, node, run_id, payload, index, outputs, warnings)
                for index, payload in enumerate(payloads)
            ]
        )
        output = _merge_fan_out_results(node, results)
        await self._record(run_id, node, "succeeded" if output.ok else "failed", output.error, _failure_kind(output), _node_run_metadata(output))
        return node, output

    async def _run_fan_out_item(
        self,
        graph: DagGraph,
        node: str,
        run_id: str,
        payload: object,
        index: int,
        outputs: dict[str, NodeOutput],
        warnings: list[str],
    ) -> NodeOutput:
        node_input = NodeInput(run_id=run_id, payload=payload, metadata=self._metadata(graph, node, outputs, warnings))
        context = NodeContext(run_id, f"{node}:fanout:{index}", graph.instances[node].type, graph.name)
        return await self._execute_node(graph.instances[node], node, node_input, context)

    async def _run_node(
        self,
        graph: DagGraph,
        node: str,
        run_id: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        routed_edges: set[tuple[str, str]],
        warnings: list[str],
        run_inputs: _RunInputs,
    ) -> tuple[str, NodeOutput]:
        input_payload = self._get_node_input(graph, node, initial_payload, outputs, payloads, routed_edges, run_inputs)
        node_input = NodeInput(
            run_id=run_id,
            payload=input_payload,
            metadata=self._metadata(graph, node, outputs, warnings),
        )
        context = NodeContext(
            run_id=run_id,
            instance_id=node,
            node_type=graph.instances[node].type,
            dag_name=graph.name,
        )
        await self._record(run_id, node, "running")
        output = await self._execute_node(graph.instances[node], node, node_input, context)
        await self._record(run_id, node, "succeeded" if output.ok else "failed", output.error, _failure_kind(output), _node_run_metadata(output))
        return node, output

    async def _execute_node(
        self,
        instance: DagNodeInstance,
        node: str,
        node_input: NodeInput,
        context: NodeContext,
    ) -> NodeOutput:
        if instance.loop is None:
            if instance.type == "dag" and instance.dag_ref:
                return await self._execute_sub_dag(instance, instance.dag_ref, instance.input_mapping, node_input)
            if instance.type in self.dags:
                return await self._execute_sub_dag(instance, instance.type, {}, node_input)
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
        semaphore = get_semaphore(instance.resource, self.executor.entity_store) if instance.resource else None

        async def run_iteration(index: int) -> NodeOutput:
            if semaphore:
                await semaphore.acquire()
            try:
                return await self.executor.execute(
                    node,
                    node_input,
                    NodeContext(context.run_id, f"{node}:{index}", context.node_type, context.dag_name),
                )
            finally:
                if semaphore:
                    semaphore.release()

        tasks = [asyncio.create_task(run_iteration(i)) for i in range(count)]
        completed_results: list[NodeOutput] = []
        matched = False

        try:
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    if result.ok and instance.loop and instance.loop.until:
                        if evaluate_condition(instance.loop.until, result.payload, self.executor.entity_store):
                            matched = True
                            for t in tasks:
                                if not t.done():
                                    t.cancel()
                            completed_results = [result]
                            break
                    completed_results.append(result)
                except asyncio.CancelledError:
                    pass

            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for t in tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        payload = [r.payload for r in completed_results if r.ok]
        failures = {f"{node}:{idx}": r.error or "iteration failed" for idx, r in enumerate(completed_results) if not r.ok}

        return NodeOutput(
            node_name=node,
            ok=bool(payload),
            payload=payload,
            metadata={"loop_failures": failures, "loop_until_matched": matched},
            error=None if payload else "; ".join(failures.values()) or "loop produced no output",
        )

    async def _emit_node_events(self, graph: DagGraph, node: str, payload: object) -> None:
        if self.emit is None:
            return
        instance = graph.instances[node]
        declarations: list[EmitDeclaration] = []
        if not self._is_sub_dag_instance(instance):
            declarations = list(self.nodes[instance.type].emits)
        instance_emits = instance.config.get("emits")
        if isinstance(instance_emits, list):
            declarations = [EmitDeclaration.model_validate(item) for item in instance_emits]
        for declaration in declarations:
            if declaration.condition:
                try:
                    if not evaluate_condition(declaration.condition, payload, self.executor.entity_store):
                        continue
                except Exception as exc:
                    logger.warning("node emit condition failed for %s: %s", declaration.event, exc)
                    continue
            await self.emit(declaration.event, payload)

    def _configure_wait_executor(self, stop_event: asyncio.Event) -> None:
        if self.trigger_executor is None:
            return
        self.executor.wait_payload_reader = self.trigger_executor.wait_payload
        self.executor.wait_register = lambda wait_for, consume: self.trigger_executor.register_waiter(wait_for, consume=consume)
        self.executor.wait_unregister = self.trigger_executor.unregister_waiter
        self.executor.wait_matched_tokens = self.trigger_executor.matched_waiter_tokens
        self.executor.wait_consumer = self.trigger_executor.events.consume
        self.executor.wait_recorder = self._record
        self.executor.wait_stop_event = stop_event

    async def _execute_serial_loop(
        self,
        instance: DagNodeInstance,
        node: str,
        node_input: NodeInput,
        context: NodeContext,
    ) -> NodeOutput:
        count = instance.loop.count if instance.loop and instance.loop.count is not None else 1
        semaphore = get_semaphore(instance.resource, self.executor.entity_store) if instance.resource else None
        current_input = node_input
        last: NodeOutput | None = None
        for index in range(count):
            if semaphore:
                await semaphore.acquire()
            try:
                last = await self.executor.execute(
                    node,
                    current_input,
                    NodeContext(context.run_id, f"{node}:{index}", context.node_type, context.dag_name),
                )
            finally:
                if semaphore:
                    semaphore.release()
            if not last.ok:
                return last
            if instance.loop.until and evaluate_condition(instance.loop.until, last.payload, self.executor.entity_store):
                break
            current_input = NodeInput(
                run_id=node_input.run_id,
                payload=last.payload,
                metadata=node_input.metadata,
            )
        return last or NodeOutput(node_name=node, ok=False, error="loop produced no output")

    async def _execute_sub_dag(
        self,
        instance: DagNodeInstance,
        dag_ref: str,
        input_mapping: dict[str, str] | str,
        node_input: NodeInput,
    ) -> NodeOutput:
        limit = self.executor.system.max_dag_depth
        step = DagPathStep(dag_name=dag_ref, via_node_id=instance.id)
        chain = (*self.path, step)
        seen_names = {s.dag_name for s in self.path}
        if dag_ref in seen_names:
            return NodeOutput(node_name=instance.id, ok=False, error=_format_cycle_error(chain, self.path[0].dag_name if self.path else dag_ref))
        if self.depth >= limit:
            name_chain = " -> ".join(s.dag_name for s in chain)
            return NodeOutput(node_name=instance.id, ok=False, error=f"max DAG depth exceeded: {name_chain}")
        graph = load_graph(self.dags[dag_ref], self.nodes, self.dags)
        runner = DagRunner(
            self.executor,
            recorder=self.recorder,
            edge_recorder=self.edge_recorder,
            dags=self.dags,
            nodes=self.nodes,
            dag_lifecycle=self.dag_lifecycle,
            depth=self.depth + 1,
            path=(*self.path, step),
        )
        child_run_id = uuid4().hex
        mapped = self._resolve_input_mapping(node_input.payload, input_mapping)
        if self.dag_lifecycle is not None:
            await self.dag_lifecycle(child_run_id, dag_ref, "started", None)
        try:
            result = await runner.run(
                graph,
                child_run_id,
                node_input.payload,
                source_shared_inputs=mapped.source_shared_inputs,
                node_inputs=mapped.node_inputs,
                append_nodes=mapped.append_nodes,
            )
        except DagError as exc:
            if self.dag_lifecycle is not None:
                await self.dag_lifecycle(child_run_id, dag_ref, "failed", str(exc))
            return NodeOutput(node_name=instance.id, ok=False, error=str(exc))
        if self.dag_lifecycle is not None:
            status = "succeeded" if result.ok else "failed"
            error = "; ".join(result.failures.values()) or None
            await self.dag_lifecycle(child_run_id, dag_ref, status, error)
        if result.ok:
            return NodeOutput(
                node_name=instance.id,
                ok=True,
                payload=result.payload,
                metadata={
                    "sub_dag_run_id": child_run_id,
                    "parent_run_id": node_input.run_id,
                    "parent_node": instance.id,
                    "sub_dag_failures": result.failures,
                    "warnings": result.warnings,
                },
            )
        error = "; ".join(result.failures.values()) or "sub DAG failed"
        return NodeOutput(
            node_name=instance.id,
            ok=False,
            metadata={"sub_dag_run_id": child_run_id, "parent_run_id": node_input.run_id, "parent_node": instance.id},
            error=error,
        )

    async def _execute_dag_node_config(
        self,
        config: DagNodeConfig,
        node_name: str,
        node_input: NodeInput,
        _context: NodeContext,
    ) -> NodeOutput:
        instance = self.executor.instances.get(node_name)
        if instance is None:
            return NodeOutput(node_name=node_name, ok=False, error=f"missing dag node instance: {node_name}")
        if config.dag_ref not in self.dags:
            return NodeOutput(node_name=node_name, ok=False, error=f"missing dag config: {config.dag_ref}")
        return await self._execute_sub_dag(instance, config.dag_ref, config.input_mapping, node_input)

    def _resolve_input_mapping(self, payload: object, input_mapping: dict[str, str] | str) -> _RunInputs:
        if isinstance(input_mapping, str):
            return self._resolve_input_mapping_entity(payload, input_mapping)
        return _RunInputs(_mapped_input(payload, input_mapping), {}, set())

    def _resolve_input_mapping_entity(self, payload: object, ref: str) -> _RunInputs:
        entity_store = self.executor.entity_store
        if entity_store is None:
            raise DagError(f"InputMapping entity not found: {ref}")
        try:
            entity = entity_store.resolve(_input_mapping_ref(ref))
        except Exception as exc:
            raise DagError(f"InputMapping entity not found: {ref}") from exc
        attrs = entity.attributes
        shared = _mapped_input(payload, _str_mapping(attrs.get("shared")))
        nodes = {}
        for node, mapping in _node_input_mappings(attrs.get("nodes")).items():
            mapped = _mapped_input(payload, mapping)
            if mapped is not _MISSING:
                nodes[node] = mapped
        append_nodes = set(_str_list(attrs.get("append_nodes")))
        return _RunInputs(shared, nodes, append_nodes)

    def _is_sub_dag_instance(self, instance: DagNodeInstance) -> bool:
        return (instance.type == "dag" and instance.dag_ref in self.dags) or instance.type in self.dags

    async def _record(
        self,
        run_id: str,
        node: str,
        status: str,
        error: str | None = None,
        failure_kind: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self.recorder is not None:
            await self.recorder(run_id, node, status, error, failure_kind, metadata)

    async def _record_edge_inputs(
        self,
        run_id: str,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> None:
        if self.edge_recorder is None:
            return
        for upstream in graph.reverse_edges[node]:
            await self.edge_recorder(self._edge_input_fact(run_id, graph, upstream, node, outputs, routed_edges))

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
        values: list[object] = []
        for name in upstreams:
            output = outputs.get(name)
            if output is None or (name, node) not in routed_edges:
                continue
            if output.ok:
                if output.payload is not None:
                    values.append(payloads[name])
        if not values:
            return []
        if len(values) == 1:
            return values[0]
        return collect(values)

    def _get_node_input(
        self,
        graph: DagGraph,
        node: str,
        initial_payload: object,
        outputs: dict[str, NodeOutput],
        payloads: dict[str, object],
        routed_edges: set[tuple[str, str]],
        run_inputs: _RunInputs,
    ) -> object:
        if self._is_source_node(graph, node):
            base = graph.instances[node].config.get("default_entity", initial_payload)
            current = run_inputs.source_shared_inputs if run_inputs.source_shared_inputs is not None else base
        else:
            current = self._input_payload(graph, node, initial_payload, outputs, payloads, routed_edges)
        if node not in run_inputs.node_inputs:
            return current
        override = run_inputs.node_inputs[node]
        return self._merge(current, override) if node in run_inputs.append_nodes else override

    def _is_source_node(self, graph: DagGraph, node: str) -> bool:
        return not graph.reverse_edges[node]

    @staticmethod
    def _merge(base: object, override: object) -> object:
        if isinstance(base, dict) and isinstance(override, dict):
            return {**base, **override}
        return override

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
        edge_inputs: list[dict[str, object]] = []
        for upstream in graph.reverse_edges[node]:
            fact = self._edge_input_fact("", graph, upstream, node, outputs, set())
            edge_inputs.append(
                {
                    "from_node_id": fact.from_node_id,
                    "to_node_id": fact.to_node_id,
                    "edge_optional": fact.edge_optional,
                    "status": fact.status,
                    "has_payload": fact.has_payload,
                    "error_summary": fact.error_summary,
                }
            )
        if edge_inputs:
            metadata["edge_inputs"] = edge_inputs
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
        for upstream in upstreams:
            output = outputs[upstream]
            if output.ok:
                if (upstream, node) in routed_edges:
                    continue
                return False
            if (upstream, node) in graph.optional_edges:
                continue
            if self._source_failure_can_be_skipped(graph, upstream, node, outputs, routed_edges):
                continue
            return False
        return True

    def _blocked_by_required_failure(
        self,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> bool:
        upstreams = graph.reverse_edges[node]
        return bool(upstreams) and all(upstream in outputs for upstream in upstreams) and bool(
            self._blocking_required_failures(graph, node, outputs, routed_edges)
        )

    def _upstream_failure_error(
        self,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> str:
        blocked = [f"{upstream}: {outputs[upstream].error or 'node failed'}" for upstream in self._blocking_required_failures(graph, node, outputs, routed_edges)]
        return "required upstream failed: " + "; ".join(blocked)

    def _blocking_required_failures(
        self,
        graph: DagGraph,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> list[str]:
        return [
            upstream
            for upstream in graph.reverse_edges[node]
            if upstream in outputs
            and not outputs[upstream].ok
            and (upstream, node) not in graph.optional_edges
            and not self._source_failure_can_be_skipped(graph, upstream, node, outputs, routed_edges)
        ]

    def _source_failure_can_be_skipped(
        self,
        graph: DagGraph,
        upstream: str,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> bool:
        upstream_config = self.nodes.get(graph.instances[upstream].type)
        return (
            getattr(upstream_config, "role", None) == "source"
            and any(
                other != upstream
                and other in outputs
                and outputs[other].ok
                and outputs[other].payload is not None
                and (other, node) in routed_edges
                for other in graph.reverse_edges[node]
            )
        )

    def _edge_input_fact(
        self,
        run_id: str,
        graph: DagGraph,
        upstream: str,
        node: str,
        outputs: dict[str, NodeOutput],
        routed_edges: set[tuple[str, str]],
    ) -> EdgeInputFact:
        output = outputs.get(upstream)
        status = "unknown"
        has_payload = False
        error_summary = None
        if output is not None and output.ok:
            has_payload = output.payload is not None and (not routed_edges or (upstream, node) in routed_edges)
            status = "available" if has_payload else "empty"
        elif output is not None and output.metadata.get("runtime_status") == "unknown":
            status = "unknown"
        elif output is not None:
            status = "failed"
            error_summary = output.error or "node failed"
        return EdgeInputFact(
            run_id=run_id,
            from_node_id=upstream,
            to_node_id=node,
            edge_optional=(upstream, node) in graph.optional_edges,
            status=status,
            has_payload=has_payload,
            error_summary=error_summary,
        )

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

    def _has_required_failure(
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
            and self._blocked_by_required_failure(graph, node, outputs, routed_edges)
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
        ) or self._has_required_failure(
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
        try:
            done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for item in blocked:
                item.released.clear()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
        except asyncio.CancelledError:
            for task in wait_tasks:
                task.cancel()
            await asyncio.gather(*wait_tasks, return_exceptions=True)
            raise

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
        return [payloads[node] for node in sinks if node in payloads]


def collect(values: Sequence[object]) -> list[object]:
    collected: list[object] = []
    for value in values:
        if isinstance(value, list):
            collected.extend(value)
        else:
            collected.append(value)
    return collected


def _failure_kind(output: NodeOutput) -> str | None:
    value = output.metadata.get("failure_kind")
    if isinstance(value, str):
        return value
    return None if output.ok else "execution_failed"


def _node_run_metadata(output: NodeOutput) -> dict[str, object] | None:
    keys = ("parent_run_id", "sub_dag_run_id", "parent_node")
    metadata = {key: output.metadata[key] for key in keys if key in output.metadata}
    return metadata or None


def _mapped_input(payload: object, input_mapping: dict[str, str] | str) -> object:
    if not input_mapping:
        return payload
    if isinstance(input_mapping, str):
        return _path_value(payload, input_mapping, _MISSING)
    return {name: value for name, path in input_mapping.items() if (value := _path_value(payload, path, _MISSING)) is not _MISSING}


_MISSING = object()


def _path_value(payload: object, path: str, default: object) -> object:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return default
    return current


def _input_mapping_ref(ref: str) -> str:
    if ref.startswith("entity://"):
        name = ref.removeprefix("entity://")
        return f"input_mapping:{name}"
    return ref


def _str_mapping(value: object) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}


def _node_input_mappings(value: object) -> dict[str, dict[str, str] | str]:
    if not isinstance(value, dict):
        return {}
    mappings: dict[str, dict[str, str] | str] = {}
    for node, mapping in value.items():
        mappings[str(node)] = mapping if isinstance(mapping, str) else _str_mapping(mapping)
    return mappings


def _str_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


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
