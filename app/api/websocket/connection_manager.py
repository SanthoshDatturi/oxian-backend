from collections import defaultdict
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        self.user_rooms: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.user_rooms[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if websocket in self.user_rooms[user_id]:
            self.user_rooms[user_id].remove(websocket)

    async def send_to_user(self, user_id: str, message: dict):
        sockets = self.user_rooms.get(user_id, [])
        for ws in sockets:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                self.disconnect(user_id, ws)


manager = ConnectionManager()
