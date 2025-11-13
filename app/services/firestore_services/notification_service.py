import uuid
import json
import os
import asyncio
import logging
from typing import List, Optional
from firebase_admin import firestore
from google.cloud import pubsub_v1
from google.api_core import exceptions as google_api_exceptions
from app.schemas.notification import NotificationCreate, NotificationRead
from app.schemas.enums import NotificationStatusEnum
from app.core.config import settings # Import settings
from google.cloud.firestore_v1.base_document import DocumentSnapshot # Import DocumentSnapshot

logger = logging.getLogger(__name__)

# --- Pub/Sub Initialization ---
if settings.PUBSUB_EMULATOR_HOST:
    os.environ["PUBSUB_EMULATOR_HOST"] = settings.PUBSUB_EMULATOR_HOST
    logger.info(f"Using Pub/Sub emulator at {settings.PUBSUB_EMULATOR_HOST}")

publisher = pubsub_v1.PublisherClient()
project_id = os.getenv("PUBSUB_PROJECT_ID", settings.GCP_PROJECT_ID)
notification_topic_name = "empathy-hub-notifications"
notification_topic_path = publisher.topic_path(project_id, notification_topic_name)

# Ensure notification topic exists
try:
    publisher.create_topic(request={"name": notification_topic_path})
    logger.info(f"Pub/Sub topic {notification_topic_name} created.")
except google_api_exceptions.AlreadyExists:
    logger.info(f"Pub/Sub topic {notification_topic_name} already exists.")
except Exception as e:
    logger.error(f"Error ensuring Pub/Sub topic exists: {e}")

def get_notifications_collection():
    """Returns the 'notifications' collection reference."""
    return firestore.client().collection('notifications')

def _convert_timestamps_to_str(data):
    """Recursively converts Firestore Timestamps to ISO 8601 strings."""
    if isinstance(data, dict):
        return {k: _convert_timestamps_to_str(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_timestamps_to_str(elem) for elem in data]
    elif isinstance(data, firestore.SERVER_TIMESTAMP.__class__): # Check for Firestore Timestamp type
        # This is a placeholder for actual timestamp values.
        # When reading from Firestore, SERVER_TIMESTAMP is resolved to a DatetimeWithNanoseconds object.
        # We need to handle that specific type.
        return data # Should not happen with resolved timestamps
    elif hasattr(data, 'isoformat'): # Check if it's a datetime object
        return data.isoformat()
    return data

def create_notification(notification_in: NotificationCreate) -> dict:
    """
    Creates a new notification document in Firestore.
    """
    notifications_collection = get_notifications_collection()
    notification_id = str(uuid.uuid4())
    
    notification_data = {
        "notification_id": notification_id,
        "recipient_id": str(notification_in.recipient_id),
        "sender_id": str(notification_in.sender_id) if notification_in.sender_id else None,
        "notification_type": notification_in.notification_type.value,
        "content": notification_in.content,
        "resource_id": str(notification_in.resource_id),
        "status": notification_in.status.value,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    
    doc_ref = notifications_collection.document(notification_id)
    doc_ref.set(notification_data)

    # Retrieve the document to get server-generated timestamps
    created_doc = doc_ref.get()
    if not created_doc.exists:
        raise ValueError("Failed to create notification")

    # Convert timestamps before publishing
    serializable_notification_data = _convert_timestamps_to_str(created_doc.to_dict())

    # Publish notification to Pub/Sub
    try:
        message_data = json.dumps(serializable_notification_data).encode("utf-8")
        logger.info(f"Attempting to publish notification to {notification_topic_name}. Data: {message_data.decode('utf-8')}")
        future = publisher.publish(notification_topic_path, message_data, recipient_id=str(notification_in.recipient_id))
        # We don't await here as it's a fire-and-forget for the API response,
        # but the future will complete in the background.
        # For debugging, you might want to await it: await asyncio.wrap_future(future)
        logger.info(f"Published notification to Pub/Sub topic {notification_topic_name} for recipient {notification_in.recipient_id}.")
    except Exception as e:
        logger.error(f"Error publishing notification to Pub/Sub: {e}")

    return created_doc.to_dict()

def get_notifications_for_user(
    user_id: str,
    status: Optional[NotificationStatusEnum] = None,
    limit: int = 100
) -> List[dict]:
    """
    Retrieves a list of notifications for a specific user, optionally filtered by status.
    """
    notifications_collection = get_notifications_collection()
    query = notifications_collection.where('recipient_id', '==', user_id).order_by('created_at', direction='DESCENDING')

    if status:
        query = query.where('status', '==', status.value)
    
    docs = list(query.limit(limit).stream())
    return [doc.to_dict() for doc in docs]

def mark_notification_as_read(notification_id: str) -> Optional[dict]:
    """
    Marks a specific notification as read.
    """
    notifications_collection = get_notifications_collection()
    doc_ref = notifications_collection.document(notification_id)
    
    doc = doc_ref.get()
    if not doc.exists:
        return None

    doc_ref.update({
        "status": NotificationStatusEnum.READ.value,
        "updated_at": firestore.SERVER_TIMESTAMP,
    })
    
    updated_doc = doc_ref.get()
    return updated_doc.to_dict()

def delete_notification(notification_id: str) -> bool:
    """
    Deletes a specific notification.
    """
    notifications_collection = get_notifications_collection()
    doc_ref = notifications_collection.document(notification_id)
    
    doc = doc_ref.get()
    if not doc.exists:
        return False

    doc_ref.delete()
    return True
