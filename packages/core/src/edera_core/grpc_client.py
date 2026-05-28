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

    async def entity_create(self, type_name: str, attributes: dict[str, object]) -> dict[str, object]:
        response = await self.entities.Create(
            pb2.Entity(type=type_name, json=json.dumps(attributes)),
            metadata=_identity_metadata(self.identity),
        )
        return _entity_response(response)

    async def entity_update(self, ref: str, field: str, value: object) -> dict[str, object]:
        response = await self.entities.Update(
            pb2.Entity(id=ref, json=json.dumps({"field": field, "value": value})),
            metadata=_identity_metadata(self.identity),
        )
        return _entity_response(response)

    async def entity_delete(self, ref: str) -> dict[str, object]:
        response = await self.entities.Delete(pb2.EntityRef(ref=ref), metadata=_identity_metadata(self.identity))
        return {"deleted": bool(response.deleted)}

    async def entity_list(self, type_name: str | None = None) -> list[dict[str, object]]:
        response = await self.entities.List(pb2.EntityQuery(type=type_name or ""), metadata=_identity_metadata(self.identity))
        return [_entity_response(item) for item in response.entities]

    async def entity_search(self, expression: str, identity: str) -> list[dict[str, object]]:
        response = await self.entities.Query(pb2.QueryRequest(expression=expression, identity=identity), metadata=_identity_metadata(identity))
        return [_entity_response(item) for item in response.entities]

    async def dag_trigger(self, name: str, payload: object | None = None) -> dict[str, object]:
        response = await self.dags.Trigger(
            pb2.DagTriggerRequest(name=name, inputs_json=json.dumps(payload) if payload is not None else "")
        )
        return {"cycle_id": response.cycle_id}

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

    async def node_resume(self, node_id: str, cycle_id: str | None, prompt: str) -> dict[str, object]:
        response = await self.nodes.Resume(pb2.NodeResumeRequest(id=node_id, cycle_id=cycle_id or "", prompt=prompt))
        return {"cycle_id": response.cycle_id}

    async def node_output(self, node_id: str, cycle_id: str | None = None) -> list[dict[str, object]]:
        response = await self.nodes.Output(pb2.NodeOutputRequest(id=node_id, cycle_id=cycle_id or ""))
        return json.loads(response.json or "[]")


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
