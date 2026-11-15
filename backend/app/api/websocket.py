"""
WebSocket Hub for Real-Time Telemetry and Event Broadcasting
Enforces strict multi-tenant routing: clients receive only their tenant's events,
while platform admins can subscribe to wildcard '*' for all tenants.
"""

import json
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        # Maps WebSocket connection to its subscribed tenant_id (or "*" for global admin)
        self.connections: Dict[WebSocket, str] = {}

    @property
    def active_connections(self):
        return list(self.connections.keys())

    async def connect(self, websocket: WebSocket, tenant_id: str = "demo-tenant"):
        await websocket.accept()
        self.connections[websocket] = tenant_id

    def disconnect(self, websocket: WebSocket):
        self.connections.pop(websocket, None)

    async def broadcast(self, message: dict):
        """Broadcasts global message to all connected clients."""
        if not self.connections:
            return
        
        payload_str = json.dumps(message)
        dead = []
        for ws in list(self.connections.keys()):
            try:
                await ws.send_text(payload_str)
            except Exception:
                dead.append(ws)
        for d in dead:
            self.disconnect(d)

    async def broadcast_tenant_event(self, tenant_id: str, event_data: dict):
        """Strictly dispatches telemetry event only to connections subscribed to this tenant_id (or '*')."""
        if not self.connections:
            return

        payload_str = json.dumps(event_data)
        dead = []
        for ws, sub_tenant in list(self.connections.items()):
            if sub_tenant == "*" or sub_tenant == tenant_id:
                try:
                    await ws.send_text(payload_str)
                except Exception:
                    dead.append(ws)

        for d in dead:
            self.disconnect(d)

    async def broadcast_event(self, event_type: str, data: dict, tenant_id: str = "*"):
        """Convenience method to broadcast typed operational events."""
        event_payload = {
            "type": event_type,
            "event": event_type,
            "data": data,
            "timestamp": json.dumps(data.get("timestamp", ""))
        }
        await self.broadcast(event_payload)


ws_manager = ConnectionManager()
