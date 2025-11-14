import uuid
from typing import List, Optional, TYPE_CHECKING # Added TYPE_CHECKING
from firebase_admin import firestore
from app.schemas.chat_request import ChatRequestCreate
from app.schemas.enums import ChatRequestStatusEnum
from app.schemas.user import UserSimple
from app.services.firestore_services import user_service

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_batch import BaseBatch # Added BaseBatch for type hinting

# This service replaces the functionality of crud/crud_chat_request.py for a Firestore database.

def get_chat_requests_collection():
    """Returns the 'chat_requests' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('chat_requests')

def _format_chat_request_document(doc: firestore.DocumentSnapshot) -> Optional[dict]:
    """
    Helper function to format a chat request document into a dictionary
    that matches the ChatRequestRead schema, including fetching user details.
    """
    if not doc.exists:
        return None
    
    data = doc.to_dict()
    if not data:
        return None

    requester_id = data.get('requester_id')
    requestee_id = data.get('requestee_id')

    requester_doc = user_service.get_user_by_anonymous_id(requester_id)
    requestee_doc = user_service.get_user_by_anonymous_id(requestee_id)

    if not requester_doc or not requestee_doc:
        # This should ideally not happen if referential integrity is maintained
        # Or handle as an error/incomplete data
        return None

    requester_simple = UserSimple(
        anonymous_id=uuid.UUID(requester_doc['anonymous_id']),
        username=requester_doc['username'],
        avatar_url=requester_doc.get('avatar_url')
    )
    requestee_simple = UserSimple(
        anonymous_id=uuid.UUID(requestee_doc['anonymous_id']),
        username=requestee_doc['username'],
        avatar_url=requestee_doc.get('avatar_url')
    )

    return {
        "anonymous_request_id": data['request_id'],
        "requester_anonymous_id": uuid.UUID(requester_id),
        "requestee_anonymous_id": uuid.UUID(requestee_id),
        "initial_message": data.get('initial_message'),
        "status": ChatRequestStatusEnum(data['status']),
        "created_at": data['created_at'],
        "responded_at": data.get('responded_at'),
        "requester": requester_simple,
        "requestee": requestee_simple,
    }

def create_chat_request(request_in: ChatRequestCreate, requester_id: str) -> dict:
    """
    Creates a new chat request document in Firestore.
    """
    chat_requests_collection = get_chat_requests_collection()
    # Check for an existing pending request from this requester to this requestee
    existing_request = get_pending_request_from_to(requester_id, str(request_in.requestee_anonymous_id))
    if existing_request:
        # If a pending request exists, update its initial message
        request_doc_ref = chat_requests_collection.document(existing_request['anonymous_request_id'])
        request_doc_ref.update({
            "initial_message": request_in.initial_message,
            "created_at": firestore.SERVER_TIMESTAMP, # Update timestamp to bring it to top
        })
        updated_request_doc = request_doc_ref.get()
        return _format_chat_request_document(updated_request_doc)
        
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
    
    # Fetch and format the newly created document to ensure it matches the schema
    new_doc = chat_requests_collection.document(request_id).get()
    formatted_new_doc = _format_chat_request_document(new_doc)
    if not formatted_new_doc:
        raise ValueError("Failed to format newly created chat request.")
    return formatted_new_doc

def get_chat_request(request_id: str) -> Optional[dict]:
    """
    Retrieves a chat request document by its ID and formats it.
    """
    chat_requests_collection = get_chat_requests_collection()
    doc_ref = chat_requests_collection.document(request_id)
    doc = doc_ref.get()
    return _format_chat_request_document(doc)

def get_pending_requests_for_user(user_id: str, limit: int = 20) -> List[dict]:
    """
    Retrieves a list of pending chat requests for a specific user (where they are the requestee) and formats them.
    """
    chat_requests_collection = get_chat_requests_collection()
    query = chat_requests_collection.where('requestee_id', '==', user_id) \
                                    .where('status', '==', ChatRequestStatusEnum.PENDING.value) \
                                    .order_by('created_at', direction='DESCENDING')
    docs = query.limit(limit).stream()
    
    formatted_requests = []
    for doc in docs:
        formatted_doc = _format_chat_request_document(doc)
        if formatted_doc:
            formatted_requests.append(formatted_doc)
    return formatted_requests

def get_pending_request_between_users(user1_id: str, user2_id: str) -> Optional[dict]:
    """
    Checks for an existing pending chat request between two users, regardless of who is the requester.
    """
    chat_requests_collection = get_chat_requests_collection()
    
    # Query for user1 -> user2
    query1 = chat_requests_collection.where('requester_id', '==', user1_id) \
                                     .where('requestee_id', '==', user2_id) \
                                     .where('status', '==', ChatRequestStatusEnum.PENDING.value)
    docs1 = list(query1.limit(1).stream())
    if docs1:
        return _format_chat_request_document(docs1[0])

    # Query for user2 -> user1
    query2 = chat_requests_collection.where('requester_id', '==', user2_id) \
                                     .where('requestee_id', '==', user1_id) \
                                     .where('status', '==', ChatRequestStatusEnum.PENDING.value)
    docs2 = list(query2.limit(1).stream())
    if docs2:
        return _format_chat_request_document(docs2[0])

    return None

def get_pending_request_from_to(requester_id: str, requestee_id: str) -> Optional[dict]:
    """
    Checks for an existing pending chat request specifically from requester_id to requestee_id.
    """
    chat_requests_collection = get_chat_requests_collection()
    
    query = chat_requests_collection.where('requester_id', '==', requester_id) \
                                     .where('requestee_id', '==', requestee_id) \
                                     .where('status', '==', ChatRequestStatusEnum.PENDING.value)
    docs = list(query.limit(1).stream())
    if docs:
        return _format_chat_request_document(docs[0])
    return None

def update_request_status(request_id: str, status: ChatRequestStatusEnum) -> Optional[dict]:
    """
    Updates the status of a chat request and returns the formatted updated request.
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
    
    # Fetch and format the updated document
    updated_doc = doc_ref.get()
    return _format_chat_request_document(updated_doc)

def delete_all_chat_requests_by_user(user_id: str, batch: Optional["BaseBatch"] = None) -> int:
    """
    Deletes all chat requests where the given user_id is either the requester or the requestee.
    If a batch is provided, the delete operations are added to the batch.
    Otherwise, it commits immediately.
    Returns the count of chat requests deleted.
    """
    db = firestore.client()
    chat_requests_collection = get_chat_requests_collection()
    deleted_count = 0
    request_ids_to_delete = set()

    local_batch = batch if batch else db.batch()

    # Query for requests where the user is the requester
    requester_query = chat_requests_collection.where('requester_id', '==', user_id)
    for doc in requester_query.stream():
        request_ids_to_delete.add(doc.id)

    # Query for requests where the user is the requestee
    requestee_query = chat_requests_collection.where('requestee_id', '==', user_id)
    for doc in requestee_query.stream():
        request_ids_to_delete.add(doc.id)
    
    # Delete all unique requests
    for request_id in request_ids_to_delete:
        local_batch.delete(chat_requests_collection.document(request_id))
        deleted_count += 1
    
    if not batch: # Only commit if no batch was provided externally
        local_batch.commit()
    
    return deleted_count