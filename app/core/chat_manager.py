import logging
import json
import asyncio
import os # Import os
from typing import Dict, List, Tuple
from fastapi import WebSocket
from google.cloud import pubsub_v1
from google.api_core import exceptions as google_api_exceptions
from app import schemas
from app.core.config import settings # Import settings to get project ID

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_chat_connections: Dict[str, List[Tuple[str, WebSocket]]] = {} # Store chat connections (room_id -> list of (user_id, WebSocket))
        self.active_notification_connections: Dict[str, WebSocket] = {} # Store individual notification connections (user_id -> WebSocket)
        self.active_chat_update_connections: Dict[str, WebSocket] = {} # Store individual general chat update connections (user_id -> WebSocket)

        if settings.PUBSUB_EMULATOR_HOST:
            os.environ["PUBSUB_EMULATOR_HOST"] = settings.PUBSUB_EMULATOR_HOST
            logger.info(f"Using Pub/Sub emulator at {settings.PUBSUB_EMULATOR_HOST}")
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self.project_id = os.getenv("PUBSUB_PROJECT_ID", settings.GCP_PROJECT_ID)
        
        # Chat Pub/Sub setup
        self.chat_topic_name = "empathy-hub-chat-messages"
        self.chat_subscription_name = f"empathy-hub-chat-subscription-{settings.INSTANCE_ID}"
        self.chat_topic_path = self.publisher.topic_path(self.project_id, self.chat_topic_name)
        self.chat_subscription_path = self.subscriber.subscription_path(self.project_id, self.chat_subscription_name)
        self.chat_future = None # To hold the chat subscriber future

        # Notification Pub/Sub setup
        self.notification_topic_name = "empathy-hub-notifications"
        self.notification_subscription_name = f"empathy-hub-notifications-subscription-{settings.INSTANCE_ID}"
        self.notification_topic_path = self.publisher.topic_path(self.project_id, self.notification_topic_name)
        self.notification_subscription_path = self.subscriber.subscription_path(self.project_id, self.notification_subscription_name)
        self.notification_future = None # To hold the notification subscriber future

        self.loop = None # To hold the main event loop

        # Ensure chat topic exists
        try:
            self.publisher.create_topic(request={"name": self.chat_topic_path})
            logger.info(f"Pub/Sub topic {self.chat_topic_name} created.")
        except google_api_exceptions.AlreadyExists:
            logger.info(f"Pub/Sub topic {self.chat_topic_name} already exists.")
        except Exception as e:
            logger.error(f"Error ensuring Pub/Sub topic exists: {e}")

        # Ensure chat subscription exists
        try:
            self.subscriber.create_subscription(
                request={"name": self.chat_subscription_path, "topic": self.chat_topic_path}
            )
            logger.info(f"Pub/Sub subscription {self.chat_subscription_name} created.")
        except google_api_exceptions.AlreadyExists:
            logger.info(f"Pub/Sub subscription {self.chat_subscription_name} already exists.")
        except Exception as e:
            logger.error(f"Error ensuring Pub/Sub chat subscription exists: {e}")

        # Ensure notification topic exists (created in notification_service.py, but good to ensure here too)
        try:
            self.publisher.create_topic(request={"name": self.notification_topic_path})
            logger.info(f"Pub/Sub topic {self.notification_topic_name} created.")
        except google_api_exceptions.AlreadyExists:
            logger.info(f"Pub/Sub topic {self.notification_topic_name} already exists.")
        except Exception as e:
            logger.error(f"Error ensuring Pub/Sub notification topic exists: {e}")

        # Ensure notification subscription exists
        try:
            self.subscriber.create_subscription(
                request={"name": self.notification_subscription_path, "topic": self.notification_topic_path}
            )
            logger.info(f"Pub/Sub subscription {self.notification_subscription_name} created.")
        except google_api_exceptions.AlreadyExists:
            logger.info(f"Pub/Sub subscription {self.notification_subscription_name} already exists.")
        except Exception as e:
            logger.error(f"Error ensuring Pub/Sub notification subscription exists: {e}")

    async def connect_chat(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        if room_id not in self.active_chat_connections:
            self.active_chat_connections[room_id] = []
        self.active_chat_connections[room_id].append((user_id, websocket))
        logger.info(f"WebSocket (chat) connected: user_id={user_id}, room_id={room_id}. Active connections in room: {len(self.active_chat_connections[room_id])}")

    def disconnect_chat(self, websocket: WebSocket, room_id: str, user_id: str):
        if room_id in self.active_chat_connections:
            connection_to_remove = (user_id, websocket)
            if connection_to_remove in self.active_chat_connections[room_id]:
                self.active_chat_connections[room_id].remove(connection_to_remove)
                logger.info(f"WebSocket (chat) disconnected: user_id={user_id}, room_id={room_id}. Remaining connections in room: {len(self.active_chat_connections[room_id])}")
                if not self.active_chat_connections[room_id]:
                    del self.active_chat_connections[room_id]
                    logger.info(f"Room {room_id} is now empty and removed.")

    async def connect_notification(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_notification_connections[user_id] = websocket
        logger.info(f"WebSocket (notification) connected for user: {user_id}")

    def disconnect_notification(self, user_id: str):
        if user_id in self.active_notification_connections:
            del self.active_notification_connections[user_id]
            logger.info(f"WebSocket (notification) disconnected for user: {user_id}")

    async def connect_chat_updates(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_chat_update_connections[user_id] = websocket
        logger.info(f"WebSocket (chat updates) connected for user: {user_id}")

    def disconnect_chat_updates(self, user_id: str):
        if user_id in self.active_chat_update_connections:
            del self.active_chat_update_connections[user_id]
            logger.info(f"WebSocket (chat updates) disconnected for user: {user_id}")

    async def send_personal_message(self, websocket: WebSocket, message: str):
        """Sends a direct message to a specific WebSocket connection."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message to WebSocket: {e}")

    async def publish_chat_message_to_pubsub(self, room_id: str, message_payload: dict):
        """Publishes a chat message to the Pub/Sub topic."""
        try:
            message_data = json.dumps(message_payload).encode("utf-8")
            future = self.publisher.publish(self.chat_topic_path, message_data, room_id=room_id)
            await asyncio.wrap_future(future) # Await the future to ensure message is published
            logger.info(f"Published chat message to Pub/Sub topic {self.chat_topic_name} for room {room_id}.")
        except Exception as e:
            logger.error(f"Error publishing chat message to Pub/Sub: {e}")

    async def _chat_pubsub_callback(self, message: pubsub_v1.subscriber.message.Message):
        """Callback for when a chat message is received from Pub/Sub."""
        try:
            message.ack() # Acknowledge the message immediately
            data = json.loads(message.data.decode("utf-8"))
            room_id = message.attributes.get("room_id")
            sender_id = data.get("sender_id") # Assuming sender_id is in the message payload
            
            # Broadcast to specific chat room WebSockets
            if room_id and room_id in self.active_chat_connections:
                ws_message = schemas.WebSocketMessage(
                    type="new_chat_message", # Differentiate message type
                    payload=data
                )
                message_str = ws_message.model_dump_json()
                logger.info(f"Broadcasting chat message to room {room_id}: {message_str}")
                logger.info(f"Received chat message from Pub/Sub for room {room_id}. Broadcasting to local clients.")

                for recipient_id, connection in self.active_chat_connections[room_id]:
                    try:
                        await connection.send_text(message_str)
                        logger.debug(f"Chat message sent to user {recipient_id} in room {room_id}.")
                    except Exception as e:
                        logger.error(f"Error sending chat message to local WebSocket for user {recipient_id} in room {room_id}: {e}")
            else:
                logger.debug(f"Received Pub/Sub chat message for room {room_id} but no active local connections or room not found.")
            
            # Also broadcast to general chat update WebSockets for all participants of the room
            # This requires knowing all participants of the room, which is not directly available in the message attributes.
            # For now, we'll assume the message payload contains enough info or we'll fetch it.
            # A more robust solution might involve publishing to a user-specific topic for chat updates.
            # For simplicity, let's assume the message payload contains the recipient_id for general updates.
            # Or, we can iterate through all active_chat_update_connections and check if they are participants of the room.
            # For now, let's just send to the sender's general chat update connection if active.
            if sender_id and sender_id in self.active_chat_update_connections:
                websocket = self.active_chat_update_connections[sender_id]
                ws_message = schemas.WebSocketMessage(
                    type="chat_update", # Differentiate message type for general updates
                    payload=data
                )
                message_str = ws_message.model_dump_json()
                logger.info(f"Broadcasting chat update to sender {sender_id}: {message_str}")
                try:
                    await websocket.send_text(message_str)
                    logger.debug(f"Chat update sent to sender {sender_id}.")
                except Exception as e:
                    logger.error(f"Error sending chat update to WebSocket for sender {sender_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing Pub/Sub chat message: {e}", exc_info=True)

    async def _notification_pubsub_callback(self, message: pubsub_v1.subscriber.message.Message):
        """Callback for when a notification message is received from Pub/Sub."""
        try:
            message.ack() # Acknowledge the message immediately
            raw_message_data = message.data.decode("utf-8")
            logger.info(f"Pub/Sub notification received. Raw data: {raw_message_data}")
            notification_data = json.loads(raw_message_data)
            recipient_id = notification_data.get("recipient_id") # Assuming recipient_id is in the notification payload
            logger.info(f"Extracted recipient_id: {recipient_id}")

            if recipient_id and recipient_id in self.active_notification_connections:
                logger.info(f"Active notification connection found for recipient_id: {recipient_id}")
                websocket = self.active_notification_connections[recipient_id]
                ws_message = schemas.WebSocketMessage(
                    type="new_notification", # Differentiate message type
                    payload=notification_data
                )
                message_str = ws_message.model_dump_json()
                logger.info(f"Attempting to broadcast notification to user {recipient_id}: {message_str}")
                try:
                    await websocket.send_text(message_str)
                    logger.info(f"Notification successfully sent to user {recipient_id}.")
                except Exception as e:
                    logger.error(f"Error sending notification to WebSocket for user {recipient_id}: {e}")
            else:
                logger.info(f"Received Pub/Sub notification for recipient {recipient_id} but no active connection found.")
        except Exception as e:
            logger.error(f"Error processing Pub/Sub notification message: {e}", exc_info=True)

    def start_pubsub_subscriber(self):
        """Starts the Pub/Sub subscribers in a background task."""
        if self.loop is None: # Ensure loop is obtained only once
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.error("No running event loop to attach the Pub/Sub subscriber to.")
                return

        def chat_callback_wrapper(message):
            if self.loop:
                asyncio.run_coroutine_threadsafe(self._chat_pubsub_callback(message), self.loop)
            else:
                logger.error("Event loop not available for Pub/Sub chat callback.")
                message.nack()

        def notification_callback_wrapper(message):
            if self.loop:
                asyncio.run_coroutine_threadsafe(self._notification_pubsub_callback(message), self.loop)
            else:
                logger.error("Event loop not available for Pub/Sub notification callback.")
                message.nack()

        if self.chat_future is None or self.chat_future.done():
            logger.info(f"Starting Pub/Sub chat subscriber for subscription {self.chat_subscription_name}...")
            self.chat_future = self.subscriber.subscribe(self.chat_subscription_path, callback=chat_callback_wrapper)
            logger.info(f"Pub/Sub chat subscriber started. Listening on {self.chat_subscription_path}")
        else:
            logger.info("Pub/Sub chat subscriber already running.")

        if self.notification_future is None or self.notification_future.done():
            logger.info(f"Starting Pub/Sub notification subscriber for subscription {self.notification_subscription_name}...")
            self.notification_future = self.subscriber.subscribe(self.notification_subscription_path, callback=notification_callback_wrapper)
            logger.info(f"Pub/Sub notification subscriber started. Listening on {self.notification_subscription_path}")
        else:
            logger.info("Pub/Sub notification subscriber already running.")


    def stop_pubsub_subscriber(self):
        """Stops the Pub/Sub subscribers."""
        if self.chat_future and not self.chat_future.done():
            self.chat_future.cancel()
            logger.info("Pub/Sub chat subscriber stopped.")
        
        if self.notification_future and not self.notification_future.done():
            self.notification_future.cancel()
            logger.info("Pub/Sub notification subscriber stopped.")

        self.subscriber.close()
        logger.info("All Pub/Sub subscribers stopped.")

manager = ConnectionManager()