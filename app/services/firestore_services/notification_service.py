import uuid
import json
import os
import asyncio
import logging
import time # Import the time module
from typing import List, Optional, TYPE_CHECKING # Added TYPE_CHECKING
from firebase_admin import firestore
from google.cloud import pubsub_v1
from google.api_core import exceptions as google_api_exceptions
from app.schemas.notification import NotificationCreate, NotificationRead
from app.schemas.enums import NotificationStatusEnum
from app.core.config import settings # Import settings
from google.cloud.firestore_v1.base_document import DocumentSnapshot # Import DocumentSnapshot
if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_batch import BaseBatch # Added BaseBatch for type hinting

logger = logging.getLogger(__name__)

# --- Pub/Sub Initialization ---
# For live deployment, ensure PUBSUB_EMULATOR_HOST environment variable is NOT set.
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
    logger.info(f"create_notification: Generated notification_id: {notification_id}")
    logger.debug(f"create_notification: Type of notification_id before set: {type(notification_id)}")
    
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
        logger.error(f"create_notification: Failed to retrieve newly created notification with ID: {notification_id}")
        raise ValueError("Failed to create notification")
    logger.debug(f"create_notification: ID of created_doc after get: {created_doc.id}")

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

def get_notification_by_id(notification_id: str) -> Optional[dict]:
    """
    Retrieves a single notification by its ID.
    """
    notifications_collection = get_notifications_collection()
    doc_ref = notifications_collection.document(notification_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def mark_notification_as_read(notification_id: str) -> Optional[dict]:
    """
    Marks a specific notification as read.
    """
    logger.info(f"mark_notification_as_read: Received notification_id: {notification_id}")
    logger.debug(f"mark_notification_as_read: Type of notification_id: {type(notification_id)}")
    notifications_collection = get_notifications_collection()
    doc_ref = notifications_collection.document(notification_id)
    
    # Implement retry mechanism for eventual consistency
    max_retries = 5
    for i in range(max_retries):
        doc = doc_ref.get()
        logger.info(f"mark_notification_as_read: For notification_id {notification_id}, doc.exists: {doc.exists} (Attempt {i+1}/{max_retries})")
        if doc.exists:
            doc_ref.update({
                "status": NotificationStatusEnum.READ.value,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            updated_doc = doc_ref.get()
            logger.info(f"mark_notification_as_read: Successfully marked notification {notification_id} as read.")
            return updated_doc.to_dict()
        else:
            logger.warning(f"mark_notification_as_read: Notification {notification_id} not found on attempt {i+1}/{max_retries}. Retrying...")
            time.sleep(0.5) # Wait for 0.5 seconds before retrying

    logger.error(f"mark_notification_as_read: Failed to find notification {notification_id} after {max_retries} attempts.")
    return None

def delete_notification(notification_id: str, batch: Optional["BaseBatch"] = None) -> bool:
    """
    Deletes a specific notification.
    If a batch is provided, the delete operation is added to the batch.
    Otherwise, it commits immediately.
    """
    notifications_collection = get_notifications_collection()
    doc_ref = notifications_collection.document(notification_id)
    
    if batch:
        batch.delete(doc_ref)
        return True
    else:
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.delete()
        return True

def mark_all_notifications_as_read_for_user(user_id: str) -> int:
    """
    Marks all unread notifications for a specific user as read.
    Returns the count of notifications marked as read.
    """
    notifications_collection = get_notifications_collection()
    
    # Query for unread notifications for the given user
    query = notifications_collection.where('recipient_id', '==', user_id).where('status', '==', NotificationStatusEnum.UNREAD.value)
    
    unread_docs = query.stream()
    
    updated_count = 0
    for doc in unread_docs:
        doc_ref = notifications_collection.document(doc.id)
        doc_ref.update({
            "status": NotificationStatusEnum.READ.value,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        updated_count += 1
    logger.info(f"Marked {updated_count} notifications as read for user {user_id}.")
    return updated_count

def delete_notifications_by_resource_id(resource_id: str) -> int:
    """
    Deletes all notifications associated with a given resource ID.
    Returns the count of notifications deleted.
    """
    notifications_collection = get_notifications_collection()
    
    # Query for notifications with the given resource_id
    query = notifications_collection.where('resource_id', '==', resource_id)
    
    deleted_count = 0
    for doc in query.stream():
        doc_ref = notifications_collection.document(doc.id)
        doc_ref.delete()
        deleted_count += 1
    logger.info(f"Deleted {deleted_count} notifications for resource ID {resource_id}.")
    return deleted_count

def delete_all_notifications_by_user(user_id: str, batch: Optional["BaseBatch"] = None) -> int:
    """
    Deletes all notifications where the given user_id is either the recipient or the sender.
    If a batch is provided, the delete operations are added to the batch.
    Otherwise, it commits immediately (though this function is intended to be called with a batch).
    Returns the count of notifications deleted.
    """
    notifications_collection = get_notifications_collection()
    deleted_count = 0
    notification_ids_to_delete = set()

    # Query for notifications where the user is the recipient
    recipient_query = notifications_collection.where('recipient_id', '==', user_id)
    for doc in recipient_query.stream():
        notification_ids_to_delete.add(doc.id)

    # Query for notifications where the user is the sender
    sender_query = notifications_collection.where('sender_id', '==', user_id)
    for doc in sender_query.stream():
        notification_ids_to_delete.add(doc.id)
    
    # Delete all unique notifications
    for notification_id in notification_ids_to_delete:
        # Pass the batch to delete_notification
        if delete_notification(notification_id, batch):
            deleted_count += 1
    
    logger.info(f"Deleted {deleted_count} notifications for user {user_id} (as recipient or sender).")
    return deleted_count