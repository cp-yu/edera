from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import grpc

from stockimformation_core.grpc_runtime import load_rig_proto


class RigGrpcClient:
    def __init__(
        self,
        address: str | None = None,
        data_dir: Path | None = None,
        allow_insecure: bool = False,
        force_insecure: bool = False,
    ) -> None:
        self.data_dir = data_dir or Path.home() / ".rig"
        self.address = address or _daemon_addr(self.data_dir)
        self._proto = load_rig_proto()
        if force_insecure:
            self._channel = grpc.aio.insecure_channel(self.address)
        else:
            credentials = _channel_credentials()
            if credentials is None and not (allow_insecure or os.environ.get("RIG_ENV") == "dev"):
                raise FileNotFoundError("gRPC client certificate files are required")
            self._channel = grpc.aio.secure_channel(self.address, credentials) if credentials is not None else grpc.aio.insecure_channel(self.address)
        self.entities = self._proto.pb2_grpc.EntityServiceStub(self._channel)
        self.dags = self._proto.pb2_grpc.DagServiceStub(self._channel)
        self.nodes = self._proto.pb2_grpc.NodeServiceStub(self._channel)
        self.system = self._proto.pb2_grpc.SystemServiceStub(self._channel)

    async def close(self) -> None:
        await self._channel.close()

    async def health(self) -> dict[str, object]:
        response = await self.system.Health(self._proto.pb2.HealthRequest())
        return {"ok": bool(response.ok)}

    async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
        request = self._proto.pb2.EventSubscribeRequest(node_id=node_id, dag_name=dag_name)
        async for event in self.system.SubscribeEvents(request):
            yield {"type": event.type, "payload": json.loads(event.json or "{}")}

    async def init_client(self, common_name: str) -> dict[str, str]:
        response = await self.system.InitClient(self._proto.pb2.ClientInitRequest(common_name=common_name))
        return {
            "client_cert_pem": response.client_cert_pem,
            "client_key_pem": response.client_key_pem,
            "ca_cert_pem": response.ca_cert_pem,
        }

    async def entity_get(self, ref: str) -> dict[str, object]:
        return _entity_response(await self.entities.Get(self._proto.pb2.EntityRef(ref=ref)))

    async def entity_create(self, type_name: str, attributes: dict[str, object]) -> dict[str, object]:
        response = await self.entities.Create(self._proto.pb2.Entity(type=type_name, json=json.dumps(attributes)))
        return _entity_response(response)

    async def entity_update(self, ref: str, field: str, value: object) -> dict[str, object]:
        response = await self.entities.Update(
            self._proto.pb2.Entity(id=ref, json=json.dumps({"field": field, "value": value}))
        )
        return _entity_response(response)

    async def entity_delete(self, ref: str) -> dict[str, object]:
        response = await self.entities.Delete(self._proto.pb2.EntityRef(ref=ref))
        return {"deleted": bool(response.deleted)}

    async def entity_list(self, type_name: str | None = None) -> list[dict[str, object]]:
        response = await self.entities.List(self._proto.pb2.EntityQuery(type=type_name or ""))
        return [_entity_response(item) for item in response.entities]

    async def entity_query(self, expression: str) -> list[dict[str, object]]:
        response = await self.entities.List(self._proto.pb2.EntityQuery(type=f"query:{expression}"))
        return [_entity_response(item) for item in response.entities]

    async def dag_trigger(self, name: str, payload: object | None = None) -> dict[str, object]:
        response = await self.dags.Trigger(
            self._proto.pb2.DagTriggerRequest(name=name, inputs_json=json.dumps(payload) if payload is not None else "")
        )
        return {"cycle_id": response.cycle_id}

    async def dag_status(self, name: str) -> dict[str, object]:
        response = await self.dags.Status(self._proto.pb2.DagRef(name=name))
        return json.loads(response.json or "{}")

    async def dag_edit(self, name: str, operation: str, payload: dict[str, object]) -> dict[str, object]:
        response = await self.dags.Edit(
            self._proto.pb2.DagEditRequest(name=name, operation=operation, json=json.dumps(payload))
        )
        return json.loads(response.json or "{}")

    async def node_status(self, node_id: str) -> dict[str, object]:
        response = await self.nodes.Status(self._proto.pb2.NodeRef(id=node_id))
        return {"node_id": response.id, "status": response.status}

    async def node_stop(self, node_id: str) -> dict[str, object]:
        response = await self.nodes.Stop(self._proto.pb2.NodeRef(id=node_id))
        return {"node_id": response.id, "status": response.status}

    async def node_resume(self, node_id: str, cycle_id: str | None, prompt: str) -> dict[str, object]:
        response = await self.nodes.Resume(
            self._proto.pb2.NodeResumeRequest(id=node_id, cycle_id=cycle_id or "", prompt=prompt)
        )
        return {"cycle_id": response.cycle_id}

    async def node_output(self, node_id: str, cycle_id: str | None = None) -> list[dict[str, object]]:
        response = await self.nodes.Output(self._proto.pb2.NodeOutputRequest(id=node_id, cycle_id=cycle_id or ""))
        return json.loads(response.json or "[]")


def _daemon_addr(data_dir: Path) -> str:
    if os.environ.get("RIG_DAEMON_ADDR"):
        return str(os.environ["RIG_DAEMON_ADDR"])
    config_path = data_dir / "config.json"
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        server = data.get("server")
        if isinstance(server, str) and server:
            return server
    return "127.0.0.1:9090"


def bootstrap_address(address: str) -> str:
    if os.environ.get("RIG_DAEMON_BOOTSTRAP_ADDR"):
        return str(os.environ["RIG_DAEMON_BOOTSTRAP_ADDR"])
    host, sep, port = address.rpartition(":")
    if not sep:
        return address
    try:
        return f"{host}:{int(port) + 1}"
    except ValueError:
        return address


def _channel_credentials():
    if os.environ.get("RIG_ENV") == "dev":
        return None
    cert = os.environ.get("RIG_CLIENT_CERT")
    key = os.environ.get("RIG_CLIENT_KEY")
    ca = os.environ.get("RIG_CA_CERT")
    if cert is None or key is None or ca is None:
        return None
    return grpc.ssl_channel_credentials(
        root_certificates=ca.encode(),
        private_key=key.encode(),
        certificate_chain=cert.encode(),
    )


def _entity_response(entity: Any) -> dict[str, object]:
    payload = json.loads(entity.json or "{}")
    if isinstance(payload, dict):
        return payload
    return {"id": entity.id, "type": entity.type, "attributes": payload}
