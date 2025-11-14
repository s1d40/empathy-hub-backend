import logging
import json
import asyncio
import os
from typing import Dict, List, Tuple
from fastapi import WebSocket
from google.cloud import pubsub_v1
from google.api_core import exceptions as google_api_exceptions
from app import schemas
from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_chat_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}
        self.active_notification_connections: Dict[str, WebSocket] = {}
        self.active_chat_update_connections: Dict[str, WebSocket] = {}

        # Pub/Sub setup for real-time chat
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
        self.chat_future = None

        # Notification Pub/Sub setup
        self.notification_topic_name = "empathy-hub-notifications"
        self.notification_subscription_name = f"empathy-hub-notifications-subscription-{settings.INSTANCE_ID}"
        self.notification_topic_path = self.publisher.topic_path(self.project_id, self.notification_topic_name)
        self.notification_subscription_path = self.subscriber.subscription_path(self.project_id, self.notification_subscription_name)
        self.notification_future = None

        # Chat Room Update Pub/Sub setup
        self.chat_room_update_topic_name = "empathy-hub-chat-room-updates"
        self.chat_room_update_subscription_name = f"empathy-hub-chat-room-updates-subscription-{settings.INSTANCE_ID}"
        self.chat_room_update_topic_path = self.publisher.topic_path(self.project_id, self.chat_room_update_topic_name)
        self.chat_room_update_subscription_path = self.subscriber.subscription_path(self.project_id, self.chat_room_update_subscription_name)
        self.chat_room_update_future = None

        self.loop = None

        self._ensure_pubsub_resources()

    def _ensure_pubsub_resources(self):
        """Creates all necessary Pub/Sub topics and subscriptions."""
        topics = [
            (self.chat_topic_name, self.chat_topic_path),
            (self.notification_topic_name, self.notification_topic_path),
            (self.chat_room_update_topic_name, self.chat_room_update_topic_path)
        ]
        subscriptions = [
            (self.chat_subscription_name, self.chat_topic_path, self.chat_subscription_path),
            (self.notification_subscription_name, self.notification_topic_path, self.notification_subscription_path),
            (self.chat_room_update_subscription_name, self.chat_room_update_topic_path, self.chat_room_update_subscription_path)
        ]

        for name, path in topics:
            try:
                self.publisher.create_topic(request={"name": path})
                logger.info(f"Pub/Sub topic {name} created.")
            except google_api_exceptions.AlreadyExists:
                logger.info(f"Pub/Sub topic {name} already exists.")
            except Exception as e:
                logger.error(f"Error ensuring Pub/Sub topic {name} exists: {e}")

        for name, topic_path, sub_path in subscriptions:
            try:
                self.subscriber.create_subscription(request={"name": sub_path, "topic": topic_path})
                logger.info(f"Pub/Sub subscription {name} created.")
            except google_api_exceptions.AlreadyExists:
                logger.info(f"Pub/Sub subscription {name} already exists.")
            except Exception as e:
                logger.error(f"Error ensuring Pub/Sub subscription {name} exists: {e}")

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
                if not self.active_chat_connections[room_id]:
                    del self.active_chat_connections[room_id]

    async def connect_notification(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_notification_connections[user_id] = websocket

    def disconnect_notification(self, user_id: str):
        if user_id in self.active_notification_connections:
            del self.active_notification_connections[user_id]

    async def connect_chat_updates(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_chat_update_connections[user_id] = websocket

    def disconnect_chat_updates(self, user_id: str):
        if user_id in self.active_chat_update_connections:
            del self.active_chat_update_connections[user_id]

    async def send_personal_message(self, websocket: WebSocket, message: str):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message to WebSocket: {e}")

    async def publish_chat_message_to_pubsub(self, room_id: str, message_payload: dict, participant_ids: List[str]):
        try:
            logger.debug(f"Attempting to publish chat message to Pub/Sub for room {room_id}. Message payload: {message_payload}")
            message_data = json.dumps(message_payload).encode("utf-8")
            attributes = {
                "room_id": room_id,
                "participant_ids": json.dumps(participant_ids)
            }
            future = self.publisher.publish(self.chat_topic_path, message_data, **attributes)
            await asyncio.wrap_future(future)
            logger.debug(f"Successfully published chat message to Pub/Sub for room {room_id}.")
        except Exception as e:
            logger.error(f"Error publishing chat message to Pub/Sub: {e}")

    async def publish_chat_room_update_to_pubsub(self, chat_room_data: dict, participant_ids: List[str]):
        try:
            message_data = json.dumps(chat_room_data).encode("utf-8")
            attributes = {"participant_ids": json.dumps(participant_ids)}
            future = self.publisher.publish(self.chat_room_update_topic_path, message_data, **attributes)
            await asyncio.wrap_future(future)
            logger.info(f"Published chat room update to Pub/Sub for participants.")
        except Exception as e:
            logger.error(f"Error publishing chat room update to Pub/Sub: {e}")

    async def _chat_pubsub_callback(self, message: pubsub_v1.subscriber.message.Message):
        try:
            logger.debug(f"Received chat message from Pub/Sub. Message ID: {message.message_id}")
            message.ack()
            data = json.loads(message.data.decode("utf-8"))
            room_id = message.attributes.get("room_id")
            
            if room_id and room_id in self.active_chat_connections:
                logger.debug(f"Sending chat message to active chat connections for room {room_id}.")
                ws_message = schemas.WebSocketMessage(type="new_message", payload=data)
                message_str = ws_message.model_dump_json()
                for _, connection in self.active_chat_connections[room_id]:
                    await connection.send_text(message_str)
            else:
                logger.debug(f"No active chat connections for room {room_id}. Message not sent to room-specific WebSockets.")

            participant_ids_str = message.attributes.get("participant_ids")
            if participant_ids_str:
                participant_ids = json.loads(participant_ids_str)
                logger.debug(f"Sending chat update to active chat update connections for participants: {participant_ids}.")
                ws_message = schemas.WebSocketMessage(type="chat_update", payload=data)
                message_str = ws_message.model_dump_json()
                for user_id in participant_ids:
                    if user_id in self.active_chat_update_connections:
                        await self.active_chat_update_connections[user_id].send_text(message_str)
                    else:
                        logger.debug(f"User {user_id} not in active chat update connections. Message not sent.")
        except Exception as e:
            logger.error(f"Error processing Pub/Sub chat message: {e}", exc_info=True)

    async def _notification_pubsub_callback(self, message: pubsub_v1.subscriber.message.Message):
        try:
            message.ack()
            notification_data = json.loads(message.data.decode("utf-8"))
            logger.info(f"_notification_pubsub_callback: Received notification data: {notification_data}")
            recipient_id = notification_data.get("recipient_id")
            if recipient_id and recipient_id in self.active_notification_connections:
                ws_message = schemas.WebSocketMessage(type="new_notification", payload=notification_data)
                await self.active_notification_connections[recipient_id].send_text(ws_message.model_dump_json())
        except Exception as e:
            logger.error(f"Error processing Pub/Sub notification message: {e}", exc_info=True)

    async def _chat_room_update_pubsub_callback(self, message: pubsub_v1.subscriber.message.Message):
        try:
            message.ack()
            chat_room_data = json.loads(message.data.decode("utf-8"))
            participant_ids_str = message.attributes.get("participant_ids")
            if participant_ids_str:
                participant_ids = json.loads(participant_ids_str)
                ws_message = schemas.WebSocketMessage(type="new_chat_room", payload=chat_room_data)
                message_str = ws_message.model_dump_json()
                for user_id in participant_ids:
                    if user_id in self.active_chat_update_connections:
                        await self.active_chat_update_connections[user_id].send_text(message_str)
                        logger.info(f"Sent new_chat_room update to user {user_id}")
        except Exception as e:
            logger.error(f"Error processing Pub/Sub chat room update: {e}", exc_info=True)

    def start_pubsub_subscriber(self):
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.error("No running event loop to attach the Pub/Sub subscriber to.")
                return

        def callback_wrapper(callback_func):
            def wrapper(message):
                if self.loop:
                    asyncio.run_coroutine_threadsafe(callback_func(message), self.loop)
                else:
                    logger.error(f"Event loop not available for {callback_func.__name__}.")
                    message.nack()
            return wrapper

        if self.chat_future is None or self.chat_future.done():
            self.chat_future = self.subscriber.subscribe(self.chat_subscription_path, callback=callback_wrapper(self._chat_pubsub_callback))
            logger.info(f"Pub/Sub chat subscriber started on {self.chat_subscription_path}")

        if self.notification_future is None or self.notification_future.done():
            self.notification_future = self.subscriber.subscribe(self.notification_subscription_path, callback=callback_wrapper(self._notification_pubsub_callback))
            logger.info(f"Pub/Sub notification subscriber started on {self.notification_subscription_path}")

        if self.chat_room_update_future is None or self.chat_room_update_future.done():
            self.chat_room_update_future = self.subscriber.subscribe(self.chat_room_update_subscription_path, callback=callback_wrapper(self._chat_room_update_pubsub_callback))
            logger.info(f"Pub/Sub chat room update subscriber started on {self.chat_room_update_subscription_path}")

    def stop_pubsub_subscriber(self):
        if self.chat_future and not self.chat_future.done():
            self.chat_future.cancel()
        if self.notification_future and not self.notification_future.done():
            self.notification_future.cancel()
        if self.chat_room_update_future and not self.chat_room_update_future.done():
            self.chat_room_update_future.cancel()
        self.subscriber.close()
        logger.info("All Pub/Sub subscribers stopped.")

manager = ConnectionManager()