"""
WebSocket Manager - 实时消息推送
用于网格员端和居民端之间的实时对话通知
"""
import json
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        # report_id -> set of websocket connections
        self.subscriptions: Dict[int, Set[WebSocket]] = {}
        # websocket -> set of report_ids (for cleanup)
        self.connections: Dict[WebSocket, Set[int]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        # Unsubscribe from all reports
        report_ids = self.connections.pop(websocket, set())
        for rid in report_ids:
            if rid in self.subscriptions:
                self.subscriptions[rid].discard(websocket)
                if not self.subscriptions[rid]:
                    del self.subscriptions[rid]

    def subscribe(self, websocket: WebSocket, report_ids: List[int]):
        """Subscribe a connection to specific report updates."""
        for rid in report_ids:
            if rid not in self.subscriptions:
                self.subscriptions[rid] = set()
            self.subscriptions[rid].add(websocket)
            self.connections[websocket].add(rid)

    async def notify_report_update(self, report_id: int, data: dict):
        """Notify all subscribers of a report about new updates."""
        if report_id not in self.subscriptions:
            return

        message = {
            "type": "report_updated",
            "report_id": report_id,
            "data": data
        }

        disconnected = []
        for ws in list(self.subscriptions[report_id]):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(ws)


# Global singleton instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "subscribe":
                # Subscribe to specific report IDs
                report_ids = data.get("report_ids", [])
                if report_ids:
                    manager.subscribe(websocket, report_ids)
                    await websocket.send_json({
                        "type": "subscribed",
                        "report_ids": report_ids
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
