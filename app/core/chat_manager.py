from typing import Dict, List, Tuple
from fastapi import WebSocket
from app import schemas

# NOTE: In a truly serverless environment with multiple scaled instances of Cloud Run,
# this in-memory ConnectionManager will not work as expected, because each instance
# would have its own separate list of connections.
# A production-ready solution would require a separate messaging service like
# Redis Pub/Sub or Google Cloud Pub/Sub to broadcast messages across all instances.
# For the purpose of this migration and for single-instance deployments, this manager will suffice.

class ConnectionManager:
    def __init__(self):
        # Stores active connections: Dict[room_id, List[Tuple[user_id, WebSocket]]]
        self.active_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append((user_id, websocket))

    def disconnect(self, websocket: WebSocket, room_id: str, user_id: str):
        if room_id in self.active_connections:
            connection_to_remove = (user_id, websocket)
            if connection_to_remove in self.active_connections[room_id]:
                self.active_connections[room_id].remove(connection_to_remove)
                if not self.active_connections[room_id]:
                    del self.active_connections[room_id]

    async def broadcast_to_room_dict(
        self,
        room_id: str,
        message_payload: dict,
        sender_id: str
    ):
        """
        Broadcasts a message dictionary to all users in a room.
        Block checks should be handled before calling this method.
        """
        if room_id in self.active_connections:
            ws_message = schemas.WebSocketMessage(
                type="new_message",
                payload=message_payload
            )
            message_str = ws_message.model_dump_json()

            for recipient_id, connection in self.active_connections[room_id]:
                # The block check is removed from here. It should be handled in the
                # service or endpoint layer before broadcasting.
                await connection.send_text(message_str)

    async def send_personal_message(self, websocket: WebSocket, message: str):
        await websocket.send_text(message)

manager = ConnectionManager()