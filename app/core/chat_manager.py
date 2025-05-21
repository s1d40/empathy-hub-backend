import uuid
from typing import Dict, List, Tuple
from fastapi import WebSocket
from sqlalchemy.orm import Session # For type hinting

from app import schemas, crud # For accessing crud.user_relationship
from app.schemas.enums import RelationshipTypeEnum # For RelationshipTypeEnum.BLOCK


class ConnectionManager:
    def __init__(self):
        # Stores active connections: Dict[room_anonymous_id, List[Tuple[user_anonymous_id, WebSocket]]]
        self.active_connections: Dict[uuid.UUID, List[Tuple[uuid.UUID, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, room_anonymous_id: uuid.UUID, user_anonymous_id: uuid.UUID):
        await websocket.accept()
        if room_anonymous_id not in self.active_connections:
            self.active_connections[room_anonymous_id] = []
        
        # Check if user is already connected in this room with another socket (optional, depends on desired behavior)
        # For simplicity, we'll allow multiple connections per user for now, but you might want to manage this.
        self.active_connections[room_anonymous_id].append((user_anonymous_id, websocket))

    def disconnect(self, websocket: WebSocket, room_anonymous_id: uuid.UUID, user_anonymous_id: uuid.UUID):
        if room_anonymous_id in self.active_connections:
            # Find the specific websocket instance for the user to remove
            connection_to_remove = (user_anonymous_id, websocket)
            if connection_to_remove in self.active_connections[room_anonymous_id]:
                self.active_connections[room_anonymous_id].remove(connection_to_remove)
                if not self.active_connections[room_anonymous_id]: # If room becomes empty
                    del self.active_connections[room_anonymous_id]

    async def broadcast_to_room(
        self,
        db: Session, # Added db session parameter
        room_anonymous_id: uuid.UUID,
        message_payload: schemas.ChatMessageRead,
        sender_anonymous_id: uuid.UUID
    ):
        if room_anonymous_id in self.active_connections:
            # Construct the WebSocket message
            ws_message = schemas.WebSocketMessage(
                type="new_message",
                payload=message_payload.model_dump() # Send the Pydantic model as a dict
            )
            message_str = ws_message.model_dump_json()

            for recipient_anonymous_id, connection in self.active_connections[room_anonymous_id]:
                # Optionally, don't send the message back to the original sender if the client handles it,
                # but it's often simpler to send to all and let the client ignore if it's their own.
                # if recipient_anonymous_id == sender_anonymous_id:
                #     pass # Let it send to sender as well, client can ignore.

                # --- BEGIN BLOCK CHECK BEFORE SENDING MESSAGE ---
                if recipient_anonymous_id != sender_anonymous_id: # No need to check block for sending to oneself
                    # Check if sender has blocked recipient
                    sender_blocks_recipient = crud.user_relationship.get_relationship(
                        db,
                        actor_anonymous_id=sender_anonymous_id,
                        target_anonymous_id=recipient_anonymous_id,
                        relationship_type=RelationshipTypeEnum.BLOCK
                    )
                    # Check if recipient has blocked sender
                    recipient_blocks_sender = crud.user_relationship.get_relationship(
                        db,
                        actor_anonymous_id=recipient_anonymous_id,
                        target_anonymous_id=sender_anonymous_id,
                        relationship_type=RelationshipTypeEnum.BLOCK
                    )
                    if sender_blocks_recipient or recipient_blocks_sender:
                        print(f"--- ChatManager: Message from {sender_anonymous_id} to {recipient_anonymous_id} in room {room_anonymous_id} blocked. ---")
                        continue # Skip sending message to this recipient
                # --- END BLOCK CHECK BEFORE SENDING MESSAGE ---
                await connection.send_text(message_str)

    async def send_personal_message(self, websocket: WebSocket, message: str):
        await websocket.send_text(message)

manager = ConnectionManager()