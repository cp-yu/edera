from __future__ import annotations

import json

from edera_core.service_common import json_response


class _EventService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def Emit(self, request, context):
        payload = json.loads(request.payload_json) if request.payload_json else None
        fired = await self.daemon.controller.emit(
            request.event,
            payload,
            source=request.source or "rpc",
            depth=request.depth,
        )
        return json_response(self.pb2, {"event": request.event, "fired": fired})
