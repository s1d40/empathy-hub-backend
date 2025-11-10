import uuid
from typing import List, Optional
from firebase_admin import firestore
from app.schemas.chat_request import ChatRequestCreate
from app.schemas.enums import ChatRequestStatusEnum

# This service replaces the functionality of crud/crud_chat_request.py for a Firestore database.

def get_chat_requests_collection():
    """Returns the 'chat_requests' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('chat_requests')

def create_chat_request(request_in: ChatRequestCreate, requester_id: str) -> dict:
    """
    Creates a new chat request document in Firestore.
    """
    chat_requests_collection = get_chat_requests_collection()
    # Check for an existing pending request between the two users
    existing_query = chat_requests_collection.where('requester_id', '==', requester_id) \
                                             .where('requestee_id', '==', str(request_in.requestee_anonymous_id)) \
                                             .where('status', '==', ChatRequestStatusEnum.PENDING.value)
    docs = existing_query.limit(1).stream()
    for doc in docs:
        return doc.to_dict() # Return existing pending request

    request_id = str(uuid.uuid4())
    request_data = {
        "request_id": request_id,
        "requester_id": requester_id,
        "requestee_id": str(request_in.requestee_anonymous_id),
        "initial_message": request_in.initial_message,
        "status": ChatRequestStatusEnum.PENDING.value,
        "created_at": firestore.SERVER_TIMESTAMP,
        "responded_at": None,
    }
    chat_requests_collection.document(request_id).set(request_data)
    return request_data

def get_chat_request(request_id: str) -> Optional[dict]:
    """
    Retrieves a chat request document by its ID.
    """
    chat_requests_collection = get_chat_requests_collection()
    doc_ref = chat_requests_collection.document(request_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_pending_requests_for_user(user_id: str, limit: int = 20) -> List[dict]:
    """
    Retrieves a list of pending chat requests for a specific user (where they are the requestee).
    """
    chat_requests_collection = get_chat_requests_collection()
    query = chat_requests_collection.where('requestee_id', '==', user_id) \
                                    .where('status', '==', ChatRequestStatusEnum.PENDING.value) \
                                    .order_by('created_at', direction='DESCENDING')
    docs = query.limit(limit).stream()
    return [doc.to_dict() for doc in docs]

def update_request_status(request_id: str, status: ChatRequestStatusEnum) -> Optional[dict]:
    """
    Updates the status of a chat request.
    """
    chat_requests_collection = get_chat_requests_collection()
    doc_ref = chat_requests_collection.document(request_id)
    doc = doc_ref.get()
    if not doc.exists:
        return None

    update_data = {
        "status": status.value,
        "responded_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.update(update_data)
    return doc_ref.get().to_dict()
