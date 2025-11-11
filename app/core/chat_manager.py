import logging
import json
import asyncio
from typing import Dict, List, Tuple
from fastapi import WebSocket
from google.cloud import pubsub_v1
from google.api_core import exceptions as google_api_exceptions
from app import schemas
from app.core.config import settings # Import settings to get project ID

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.project_id = settings.GCP_PROJECT_ID
        self.topic_name = "empathy-hub-chat-messages" # Use the topic created earlier
        self.subscription_name = f"empathy-hub-chat-subscription-{settings.INSTANCE_ID}" # Unique subscription per instance
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        self.subscription_path = self.subscriber.subscription_path(self.project_id, self.subscription_name)
        self.future = None # To hold the subscriber future

        # Ensure subscription exists
        try:
            self.subscriber.get_subscription(request={"subscription": self.subscription_path})
            logger.info(f"Pub/Sub subscription {self.subscription_name} already exists.")
        except google_api_exceptions.NotFound:
            logger.info(f"Creating Pub/Sub subscription {self.subscription_name}...")
            self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": self.topic_path}
            )
            logger.info(f"Pub/Sub subscription {self.subscription_name} created.")
        except Exception as e:
            logger.error(f"Error ensuring Pub/Sub subscription exists: {e}")

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

    async def publish_message_to_pubsub(self, room_id: str, message_payload: dict):
        """Publishes a message to the Pub/Sub topic."""
        try:
            message_data = json.dumps(message_payload).encode("utf-8")
            future = self.publisher.publish(self.topic_path, message_data, room_id=room_id)
            await asyncio.wrap_future(future) # Await the future to ensure message is published
            logger.info(f"Published message to Pub/Sub topic {self.topic_name} for room {room_id}.")
        except Exception as e:
            logger.error(f"Error publishing message to Pub/Sub: {e}")

    async def _pubsub_callback(self, message: pubsub_v1.subscriber.message.Message):
        """Callback for when a message is received from Pub/Sub."""
        try:
            message.ack() # Acknowledge the message immediately
            data = json.loads(message.data.decode("utf-8"))
            room_id = message.attributes.get("room_id")

            if room_id and room_id in self.active_connections:
                ws_message = schemas.WebSocketMessage(
                    type="new_message",
                    payload=data
                )
                message_str = ws_message.model_dump_json()
                logger.info(f"Received message from Pub/Sub for room {room_id}. Broadcasting to local clients.")

                for recipient_id, connection in self.active_connections[room_id]:
                    try:
                        await connection.send_text(message_str)
                        logger.debug(f"Message sent to user {recipient_id} in room {room_id}.")
                    except Exception as e:
                        logger.error(f"Error sending message to local WebSocket for user {recipient_id} in room {room_id}: {e}")
            else:
                logger.debug(f"Received Pub/Sub message for room {room_id} but no active local connections or room not found.")
        except Exception as e:
            logger.error(f"Error processing Pub/Sub message: {e}", exc_info=True)

    def start_pubsub_subscriber(self):
        """Starts the Pub/Sub subscriber in a background task."""
        if self.future is None or self.future.done():
            logger.info(f"Starting Pub/Sub subscriber for subscription {self.subscription_name}...")
            # The callback needs to be awaited, so we wrap it in an asyncio.Task
            self.future = self.subscriber.subscribe(self.subscription_path, callback=lambda message: asyncio.create_task(self._pubsub_callback(message)))
            logger.info(f"Pub/Sub subscriber started. Listening on {self.subscription_path}")
        else:
            logger.info("Pub/Sub subscriber already running.")

    def stop_pubsub_subscriber(self):
        """Stops the Pub/Sub subscriber."""
        if self.future and not self.future.done():
            self.future.cancel()
            self.subscriber.close()
            logger.info("Pub/Sub subscriber stopped.")

manager = ConnectionManager()