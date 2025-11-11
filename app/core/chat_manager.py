import logging
from typing import Dict, List, Tuple
from fastapi import WebSocket
from app import schemas

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Stores active connections: Dict[room_id, List[Tuple[user_id, WebSocket]]]
        self.active_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append((user_id, websocket))
        logger.info(f"WebSocket connected: user_id={user_id}, room_id={room_id}. Active connections in room: {len(self.active_connections[room_id])}")

    def disconnect(self, websocket: WebSocket, room_id: str, user_id: str):
        if room_id in self.active_connections:
            connection_to_remove = (user_id, websocket)
            if connection_to_remove in self.active_connections[room_id]:
                self.active_connections[room_id].remove(connection_to_remove)
                logger.info(f"WebSocket disconnected: user_id={user_id}, room_id={room_id}. Remaining connections in room: {len(self.active_connections[room_id])}")
                if not self.active_connections[room_id]:
                    del self.active_connections[room_id]
                    logger.info(f"Room {room_id} is now empty and removed.")

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
            logger.info(f"Broadcasting message to room {room_id} from sender {sender_id}. Payload: {message_payload}")

            for recipient_id, connection in self.active_connections[room_id]:
                # The block check is removed from here. It should be handled in the
                # service or endpoint layer before broadcasting.
                try:
                    await connection.send_text(message_str)
                    logger.debug(f"Message sent to user {recipient_id} in room {room_id}.")
                except Exception as e:
                    logger.error(f"Error sending message to user {recipient_id} in room {room_id}: {e}")