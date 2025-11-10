import uuid
from typing import List, Optional
from firebase_admin import firestore
from app.schemas.chat import ChatRoomCreate, ChatMessageCreate
from app.services.firestore_services import user_service

# This service replaces the functionality of crud/crud_chat.py for a Firestore database.

def get_chat_rooms_collection():
    """Returns the 'chat_rooms' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('chat_rooms')

def create_chat_room(room_in: ChatRoomCreate, initiator_id: str) -> dict:
    """
    Creates a new chat room document in Firestore.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    room_id = str(uuid.uuid4())
    
    all_participant_ids = list(set([initiator_id] + [str(p_id) for p_id in room_in.participant_anonymous_ids]))

    if not room_in.is_group and len(all_participant_ids) != 2:
        raise ValueError("Direct chats must have exactly two participants.")

    # For direct chats, check if a room already exists
    if not room_in.is_group:
        existing_room = get_direct_chat_by_participants(all_participant_ids[0], all_participant_ids[1])
        if existing_room:
            return existing_room

    room_data = {
        "room_id": room_id,
        "name": room_in.name if room_in.is_group else None,
        "is_group": room_in.is_group,
        "participants": all_participant_ids,
        "last_message": None,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    chat_rooms_collection.document(room_id).set(room_data)
    return room_data

def get_chat_room(room_id: str) -> Optional[dict]:
    """
    Retrieves a chat room document by its ID.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    doc_ref = chat_rooms_collection.document(room_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_direct_chat_by_participants(user1_id: str, user2_id: str) -> Optional[dict]:
    """
    Finds an existing direct chat room between two users.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    # This query is more complex in Firestore and requires participants to be sorted
    # to ensure the query is consistent.
    participants_sorted = sorted([user1_id, user2_id])
    
    query = chat_rooms_collection.where('is_group', '==', False).where('participants', '==', participants_sorted)
    docs = query.limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None

def get_chat_rooms_for_user(user_id: str, limit: int = 20) -> List[dict]:
    """
    Retrieves a list of chat rooms for a specific user.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    query = chat_rooms_collection.where('participants', 'array_contains', user_id).order_by('updated_at', direction='DESCENDING')
    docs = query.limit(limit).stream()
    return [doc.to_dict() for doc in docs]

def add_message_to_chat_room(room_id: str, message_in: ChatMessageCreate, sender_id: str) -> dict:
    """
    Adds a new message to a chat room's 'messages' subcollection and updates the room's 'last_message'.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    room_ref = chat_rooms_collection.document(room_id)
    message_id = str(uuid.uuid4())
    message_ref = room_ref.collection('messages').document(message_id)

    sender_data = user_service.get_user_by_anonymous_id(sender_id)
    if not sender_data:
        raise ValueError("Sender not found")

    message_data = {
        "message_id": message_id,
        "room_id": room_id,
        "content": message_in.content,
        "sender_id": sender_id,
        "sender_username": sender_data.get('username'),
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

    last_message_summary = {
        "content": message_in.content,
        "sender_id": sender_id,
        "timestamp": firestore.SERVER_TIMESTAMP,
    }

    # Use a batch write to add the message and update the room atomically
    db = firestore.client()
    batch = db.batch()
    batch.set(message_ref, message_data)
    batch.update(room_ref, {
        'last_message': last_message_summary,
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    batch.commit()

    return message_data

def get_messages_for_chat_room(room_id: str, limit: int = 50) -> List[dict]:
    """
    Retrieves a list of messages for a specific chat room.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    messages_query = chat_rooms_collection.document(room_id).collection('messages').order_by('timestamp', direction='DESCENDING')
    docs = messages_query.limit(limit).stream()
    return [doc.to_dict() for doc in docs]
