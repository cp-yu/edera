from __future__ import annotations

import json
import os
from typing import Any

import grpc

from edera_core.proto import edera_pb2 as pb2, edera_pb2_grpc as pb2_grpc


class GrpcClient:
    def __init__(
        self,
        address: str | None = None,
        *,
        identity: str | None = None,
        allow_insecure: bool = False,
        force_insecure: bool = False,
        client_cert_pem: str | None = None,
        client_key_pem: str | None = None,
        ca_cert_pem: str | None = None,
    ) -> None:
        self.address = address or _server_addr()
        self.identity = identity
        if force_insecure:
            self._channel = grpc.aio.insecure_channel(self.address)
        else:
            credentials = _channel_credentials(client_cert_pem, client_key_pem, ca_cert_pem)
            if credentials is None and not (allow_insecure or os.environ.get("EDERA_DEV") == "1"):
                raise FileNotFoundError("gRPC client certificate files are required")
            self._channel = grpc.aio.secure_channel(self.address, credentials) if credentials is not None else grpc.aio.insecure_channel(self.address)
        self.entities = pb2_grpc.EntityServiceStub(self._channel)
        self.dags = pb2_grpc.DagServiceStub(self._channel)
        self.nodes = pb2_grpc.NodeServiceStub(self._channel)
        self.system = pb2_grpc.SystemServiceStub(self._channel)
        self.graph = pb2_grpc.GraphServiceStub(self._channel)
        self.config = pb2_grpc.ConfigServiceStub(self._channel)
        self.query = pb2_grpc.QueryServiceStub(self._channel)
        self.event = pb2_grpc.EventServiceStub(self._channel)
        self.extension = pb2_grpc.ExtensionServiceStub(self._channel)

    async def close(self) -> None:
        await self._channel.close()

    async def health(self) -> dict[str, object]:
        response = await self.system.Health(pb2.HealthRequest())
        return {"ok": bool(response.ok)}

    async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
        request = pb2.EventSubscribeRequest(node_id=node_id, dag_name=dag_name)
        async for event in self.system.SubscribeEvents(request):
            yield {"type": event.type, "payload": json.loads(event.json or "{}")}

    async def init_client(self, common_name: str) -> dict[str, str]:
        response = await self.system.InitClient(pb2.ClientInitRequest(common_name=common_name))
        return {
            "client_cert_pem": response.client_cert_pem,
            "client_key_pem": response.client_key_pem,
            "ca_cert_pem": response.ca_cert_pem,
        }

    async def entity_get(self, ref: str) -> dict[str, object]:
        return _entity_response(await self.entities.Get(pb2.EntityRef(ref=ref), metadata=_identity_metadata(self.identity)))

    async def entity_create(self, type_name: str, attributes: dict[str, object], entity_id: str = "") -> dict[str, object]:
        response = await self.entities.Create(
            pb2.Entity(id=entity_id, type=type_name, json=json.dumps(attributes)),
            metadata=_identity_metadata(self.identity),
        )
        return _entity_response(response)

    async def entity_update(self, ref: str, field: str, value: object) -> dict[str, object]:
        response = await self.entities.Update(
            pb2.Entity(id=ref, json=json.dumps({"field": field, "value": value})),
            metadata=_identity_metadata(self.identity),
        )
        return _entity_response(response)

    async def entity_delete(self, ref: str, force: bool = False) -> dict[str, object]:
        response = await self.entities.Delete(pb2.EntityRef(ref=ref, force=force), metadata=_identity_metadata(self.identity))
        return {"deleted": bool(response.deleted)}

    async def entity_list(
        self,
        type_name: str | None = None,
        filters: dict[str, object] | None = None,
        dag_run_id: str | None = None,
    ) -> list[dict[str, object]]:
        response = await self.entities.List(
            pb2.EntityQuery(
                type=type_name or "",
                filters_json=json.dumps(filters or {}),
                dag_run_id=dag_run_id or "",
            ),
            metadata=_identity_metadata(self.identity),
        )
        return [_entity_response(item) for item in response.entities]

    async def entity_import(self, path: str, type_name: str | None = None) -> dict[str, object]:
        response = await self.entities.Import(
            pb2.JsonRequest(json=json.dumps({"file": path, "type": type_name or ""})),
            metadata=_identity_metadata(self.identity),
        )
        return _json_response(response)

    async def entity_export(self, type_name: str | None = None) -> dict[str, object]:
        response = await self.entities.Export(
            pb2.EntityQuery(type=type_name or ""),
            metadata=_identity_metadata(self.identity),
        )
        return _json_response(response)

    async def entity_search(self, expression: str, identity: str) -> list[dict[str, object]]:
        response = await self.entities.Query(pb2.QueryRequest(expression=expression, identity=identity), metadata=_identity_metadata(identity))
        return [_entity_response(item) for item in response.entities]

    async def entity_materialize(self, payload: dict[str, object]) -> dict[str, object]:
        response = await self.entities.Materialize(
            pb2.JsonRequest(json=json.dumps(payload)),
            metadata=_identity_metadata(self.identity),
        )
        return _json_response(response)

    async def dag_run(self, name: str, payload: object | None = None) -> dict[str, object]:
        response = await self.dags.Run(pb2.DagRunRequest(name=name, inputs_json=json.dumps(payload) if payload is not None else ""))
        return {"run_id": response.run_id}

    async def event_emit(
        self,
        event: str,
        payload: object | None = None,
        *,
        source: str = "rpc",
        depth: int = 0,
    ) -> dict[str, object]:
        return _json_response(
            await self.event.Emit(
                pb2.EmitRequest(
                    event=event,
                    payload_json=json.dumps(payload) if payload is not None else "",
                    source=source,
                    depth=depth,
                )
            )
        )

    async def dag_status(self, name: str) -> dict[str, object]:
        response = await self.dags.Status(pb2.DagRef(name=name))
        return json.loads(response.json or "{}")

    async def dag_edit(self, name: str, operation: str, payload: dict[str, object]) -> dict[str, object]:
        response = await self.dags.Edit(pb2.DagEditRequest(name=name, operation=operation, json=json.dumps(payload)))
        return json.loads(response.json or "{}")

    async def node_status(self, node_id: str) -> dict[str, object]:
        response = await self.nodes.Status(pb2.NodeRef(id=node_id))
        return {"node_id": response.id, "status": response.status}

    async def node_stop(self, node_id: str) -> dict[str, object]:
        response = await self.nodes.Stop(pb2.NodeRef(id=node_id))
        return {"node_id": response.id, "status": response.status}

    async def node_resume(self, node_id: str, run_id: str | None, prompt: str) -> dict[str, object]:
        response = await self.nodes.Resume(pb2.NodeResumeRequest(id=node_id, run_id=run_id or "", prompt=prompt))
        return {"run_id": response.run_id}

    async def node_output(self, node_id: str, run_id: str | None = None) -> list[dict[str, object]]:
        response = await self.nodes.Output(pb2.NodeOutputRequest(id=node_id, run_id=run_id or ""))
        return json.loads(response.json or "[]")

    async def query_latest_briefing(self) -> dict[str, object]:
        return _json_response(await self.query.LatestBriefing(pb2.EmptyRequest()))

    async def query_list_briefings(self, created_from: str = "", created_to: str = "", limit: int = 50) -> dict[str, object]:
        return _json_response(await self.query.ListBriefings(pb2.TimeRangeRequest(created_from=created_from, created_to=created_to, limit=limit)))

    async def query_get_briefing(self, briefing_id: str) -> dict[str, object]:
        return _json_response(await self.query.GetBriefing(pb2.NameRequest(name=briefing_id)))

    async def query_list_advices(self, stock_code: str = "", direction: str = "", created_from: str = "", created_to: str = "", limit: int = 50) -> dict[str, object]:
        return _json_response(await self.query.ListAdvices(pb2.AdviceQueryRequest(stock_code=stock_code, direction=direction, created_from=created_from, created_to=created_to, limit=limit)))

    async def query_get_advice(self, advice_id: str) -> dict[str, object]:
        return _json_response(await self.query.GetAdvice(pb2.NameRequest(name=advice_id)))

    async def query_results_summary(self, stock_code: str = "", direction: str = "", created_from: str = "", created_to: str = "") -> dict[str, object]:
        return _json_response(await self.query.ResultsSummary(pb2.AdviceQueryRequest(stock_code=stock_code, direction=direction, created_from=created_from, created_to=created_to)))

    async def query_source_health(self) -> dict[str, object]:
        return _json_response(await self.query.SourceHealth(pb2.EmptyRequest()))

    async def query_source_logs(self, source_name: str = "", limit: int = 50) -> dict[str, object]:
        return _json_response(await self.query.SourceLogs(pb2.SourceLogsRequest(source_name=source_name, limit=limit)))

    async def query_node_outputs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
        return _json_response(await self.query.NodeOutputs(pb2.NodeOutputsRequest(node_id=node_id, run_id=run_id, limit=limit)))

    async def query_node_logs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
        return _json_response(await self.query.NodeLogs(pb2.NodeOutputsRequest(node_id=node_id, run_id=run_id, limit=limit)))

    async def query_node_history(self, dag_name: str, node_id: str, limit: int = 50) -> dict[str, object]:
        return _json_response(await self.query.NodeHistory(pb2.NodeHistoryRequest(dag_name=dag_name, node_id=node_id, limit=limit)))

    async def system_pause_scheduler(self) -> dict[str, object]:
        return _json_response(await self.system.PauseScheduler(pb2.EmptyRequest()))

    async def system_resume_scheduler(self) -> dict[str, object]:
        return _json_response(await self.system.ResumeScheduler(pb2.EmptyRequest()))

    async def system_scheduler_status(self) -> dict[str, object]:
        return _json_response(await self.system.SchedulerStatus(pb2.EmptyRequest()))

    async def dag_stop(self, dag_name: str, force: bool = False) -> dict[str, object]:
        return _json_response(await self.dags.Stop(pb2.DagStopRequest(dag_name=dag_name, force=force)))

    async def dag_retry(self, dag_name: str, run_id: str = "", node_ids: list[str] | None = None, mode: str = "single", payload: object | None = None) -> dict[str, object]:
        return _json_response(
            await self.dags.Retry(
                pb2.DagRetryRequest(
                    dag_name=dag_name,
                    run_id=run_id,
                    node_ids=node_ids or [],
                    mode=mode,
                    payload_json=json.dumps(payload) if payload is not None else "",
                )
            )
        )

    async def system_create_repair_task(self, source_name: str) -> dict[str, object]:
        return _json_response(await self.system.CreateRepairTask(pb2.NameRequest(name=source_name)))

    async def graph_list_dags(self) -> dict[str, object]:
        return _json_response(await self.graph.ListDags(pb2.EmptyRequest()))

    async def graph_get_dag(self, name: str) -> dict[str, object]:
        return _json_response(await self.graph.GetDag(pb2.NameRequest(name=name)))

    async def graph_create_dag(self, name: str) -> dict[str, object]:
        return _json_response(await self.graph.CreateDag(pb2.NameRequest(name=name)))

    async def graph_save_dag(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.graph.SaveDag(pb2.NamedJsonRequest(name=name, json=json.dumps(payload))))

    async def graph_create_dag_node(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.graph.CreateDagNode(pb2.NamedJsonRequest(name=name, json=json.dumps(payload))))

    async def graph_list_node_types(self) -> dict[str, object]:
        return _json_response(await self.graph.ListNodeTypes(pb2.EmptyRequest()))

    async def graph_get_node_type(self, name: str) -> dict[str, object]:
        return _json_response(await self.graph.GetNodeType(pb2.NameRequest(name=name)))

    async def graph_save_node_type(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.graph.SaveNodeType(pb2.NamedJsonRequest(name=name, json=json.dumps(payload))))

    async def graph_create_node_type(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.graph.CreateNodeType(pb2.NamedJsonRequest(name=name, json=json.dumps(payload))))

    async def graph_delete_node_type(self, name: str) -> dict[str, object]:
        return _json_response(await self.graph.DeleteNodeType(pb2.NameRequest(name=name)))

    async def graph_list_skills(self) -> dict[str, object]:
        return _json_response(await self.graph.ListSkills(pb2.EmptyRequest()))

    async def graph_create_skill(self, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.graph.CreateSkill(pb2.JsonRequest(json=json.dumps(payload))))

    async def graph_save_skill(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.graph.SaveSkill(pb2.NamedJsonRequest(name=name, json=json.dumps(payload))))

    async def graph_delete_skill(self, name: str) -> dict[str, object]:
        return _json_response(await self.graph.DeleteSkill(pb2.NameRequest(name=name)))

    async def graph_list_handlers(self) -> dict[str, object]:
        return _json_response(await self.graph.ListHandlers(pb2.EmptyRequest()))

    async def graph_get_handler(self, name: str) -> dict[str, object]:
        return _json_response(await self.graph.GetHandler(pb2.NameRequest(name=name)))

    async def graph_save_handler(self, name: str, code: str) -> dict[str, object]:
        return _json_response(await self.graph.SaveHandler(pb2.NamedTextRequest(name=name, content=code)))

    async def graph_runtime_status(self, run_id: str = "") -> dict[str, object]:
        return _json_response(await self.graph.RuntimeStatus(pb2.RuntimeStatusRequest(run_id=run_id)))

    async def query_child_run_for_parent(self, parent_run_id: str, parent_node_id: str) -> dict[str, object]:
        return _json_response(await self.query.ChildRunForParent(pb2.ParentChildRunRequest(parent_run_id=parent_run_id, parent_node_id=parent_node_id)))

    async def config_list(self) -> dict[str, object]:
        return _json_response(await self.config.ListConfigs(pb2.EmptyRequest()))

    async def config_read_system(self) -> dict[str, object]:
        return _json_response(await self.config.ReadSystemConfig(pb2.EmptyRequest()))

    async def config_save_system(self, content: str) -> dict[str, object]:
        return _json_response(await self.config.SaveSystemConfig(pb2.TextRequest(content=content)))

    async def config_read(self, kind: str, name: str) -> dict[str, object]:
        return _json_response(await self.config.ReadConfig(pb2.ConfigFileRequest(kind=kind, name=name)))

    async def config_save(self, kind: str, name: str, content: str) -> dict[str, object]:
        return _json_response(await self.config.SaveConfig(pb2.ConfigFileContentRequest(kind=kind, name=name, content=content)))

    async def config_read_entities(self) -> dict[str, object]:
        return _json_response(await self.config.ReadEntitiesConfig(pb2.EmptyRequest()))

    async def config_save_entities(self, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.config.SaveEntitiesConfig(pb2.JsonRequest(json=json.dumps(payload))))

    async def config_list_entity_types(self) -> dict[str, object]:
        return _json_response(await self.config.ListEntityTypes(pb2.EmptyRequest()))

    async def config_create_entity_type(self, name: str, content: str) -> dict[str, object]:
        return _json_response(await self.config.CreateEntityType(pb2.ConfigFileContentRequest(name=name, content=content)))

    async def config_get_entity_type(self, name: str) -> dict[str, object]:
        return _json_response(await self.config.GetEntityType(pb2.NameRequest(name=name)))

    async def config_save_entity_type(self, name: str, content: str) -> dict[str, object]:
        return _json_response(await self.config.SaveEntityType(pb2.ConfigFileContentRequest(name=name, content=content)))

    async def config_delete_entity_type(self, name: str, cascade: bool = False) -> dict[str, object]:
        return _json_response(await self.config.DeleteEntityType(pb2.DeleteEntityTypeRequest(name=name, cascade=cascade)))

    async def config_read_entity_relations(self) -> dict[str, object]:
        return _json_response(await self.config.ReadEntityRelationsConfig(pb2.EmptyRequest()))

    async def config_save_entity_relations(self, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.config.SaveEntityRelationsConfig(pb2.JsonRequest(json=json.dumps(payload))))

    async def config_create_entity_relation(self, payload: dict[str, object]) -> dict[str, object]:
        return _json_response(await self.config.CreateEntityRelation(pb2.JsonRequest(json=json.dumps(payload))))

    async def config_delete_entity_relation(self, relation_id: str) -> dict[str, object]:
        return _json_response(await self.config.DeleteEntityRelation(pb2.NameRequest(name=relation_id)))

    async def extension_list_available(self) -> dict[str, object]:
        return _json_response(await self.extension.ListAvailable(pb2.EmptyRequest()))

    async def extension_list_installed(self) -> dict[str, object]:
        return _json_response(await self.extension.ListInstalled(pb2.EmptyRequest()))

    async def extension_show(self, name: str) -> dict[str, object]:
        return _json_response(await self.extension.Show(pb2.NameRequest(name=name)))

    async def extension_install(self, name: str) -> dict[str, object]:
        return _json_response(await self.extension.Install(pb2.NameRequest(name=name)))

    async def extension_uninstall(self, name: str, strategy: str) -> dict[str, object]:
        return _json_response(
            await self.extension.Uninstall(pb2.NamedJsonRequest(name=name, json=json.dumps({"strategy": strategy})))
        )

    async def extension_reactivate(self, name: str) -> dict[str, object]:
        return _json_response(await self.extension.Reactivate(pb2.NameRequest(name=name)))


def _server_addr() -> str:
    value = os.environ.get("EDERA_SERVER_ADDR")
    if not value:
        raise ValueError("EDERA_SERVER_ADDR not set")
    return value


def _channel_credentials(
    client_cert_pem: str | None = None,
    client_key_pem: str | None = None,
    ca_cert_pem: str | None = None,
):
    if os.environ.get("EDERA_DEV") == "1":
        return None
    cert = client_cert_pem or os.environ.get("EDERA_CLIENT_CERT")
    key = client_key_pem or os.environ.get("EDERA_CLIENT_KEY")
    ca = ca_cert_pem or os.environ.get("EDERA_CA_CERT")
    if cert is None or key is None or ca is None:
        return None
    return grpc.ssl_channel_credentials(
        root_certificates=ca.encode(),
        private_key=key.encode(),
        certificate_chain=cert.encode(),
    )


def _identity_metadata(identity: str | None) -> tuple[tuple[str, str], ...] | None:
    return (("x-edera-identity", identity),) if identity else None


def _entity_response(entity: Any) -> dict[str, object]:
    payload = json.loads(entity.json or "{}")
    if isinstance(payload, dict):
        return payload
    return {"id": entity.id, "type": entity.type, "attributes": payload}


def _json_response(response: Any) -> dict[str, object]:
    payload = json.loads(response.json or "{}")
    return payload if isinstance(payload, dict) else {"value": payload}
