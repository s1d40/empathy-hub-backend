import uuid
from typing import List, Optional
from firebase_admin import firestore
from app import schemas

from app.schemas.chat import ChatRoomCreate, ChatMessageCreate, ChatMessageRead
from app.schemas.user import UserSimple
from app.services.firestore_services import user_service
from datetime import datetime

# This service replaces the functionality of crud/crud_chat.py for a Firestore database.

def get_chat_rooms_collection():
    """Returns the 'chat_rooms' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('chat_rooms')

def _format_chat_message(message_data: dict) -> dict:
    """
    Formats a chat message dictionary from Firestore to match the ChatMessageRead schema.
    """
    if not message_data:
        return None

    message_data['id'] = message_data.get('message_id')
    message_data['anonymous_message_id'] = f"msg_{uuid.UUID(message_data.get('message_id')).hex[:8]}"


    # Format sender if sender_id exists
    if 'sender_id' in message_data:
        sender_data = user_service.get_user_by_anonymous_id(message_data['sender_id'])
        if sender_data:
            message_data['sender'] = UserSimple(
                anonymous_id=uuid.UUID(sender_data['anonymous_id']),
                username=sender_data['username'],
                avatar_url=sender_data.get('avatar_url')
            )

    # Convert timestamp to datetime object
    if 'timestamp' in message_data and isinstance(message_data['timestamp'], str):
        message_data['created_at'] = datetime.fromisoformat(message_data['timestamp'])
    elif 'timestamp' in message_data and isinstance(message_data['timestamp'], (int, float)):
        message_data['created_at'] = datetime.fromtimestamp(message_data['timestamp'])
    else:
        message_data['created_at'] = message_data.get('timestamp')

    return message_data

def _format_chat_room(room_dict: dict) -> Optional[dict]:
    """
    Formats a chat room dictionary from Firestore to match the ChatRoomRead schema.
    """
    if not room_dict:
        return None

    # Ensure room_id is present and convert to UUID
    room_id_str = room_dict.pop('room_id', None)
    if not room_id_str:
        return None # Or raise an error, depending on desired behavior
    room_dict['anonymous_room_id'] = uuid.UUID(room_id_str)

    # Convert Firestore Timestamps to datetime objects
    # created_at is required by schema, so it must be a datetime
    created_at_ts = room_dict.get('created_at')
    if isinstance(created_at_ts, datetime):
        room_dict['created_at'] = created_at_ts
    elif isinstance(created_at_ts, firestore.SERVER_TIMESTAMP.__class__):
        # This should ideally not happen if the document is read after being written
        # If it does, it means the timestamp hasn't been resolved by Firestore yet.
        # For now, we'll use datetime.now() as a fallback, but this indicates a potential race condition
        # or an issue with how the document is being read.
        room_dict['created_at'] = datetime.now()
    else:
        # Fallback for cases where created_at might be missing or not a timestamp
        room_dict['created_at'] = datetime.now() # Ensure it's always a datetime

    updated_at_ts = room_dict.get('updated_at')
    if isinstance(updated_at_ts, datetime):
        room_dict['updated_at'] = updated_at_ts
    elif isinstance(updated_at_ts, firestore.SERVER_TIMESTAMP.__class__):
        room_dict['updated_at'] = datetime.now() # Fallback
    else:
        room_dict['updated_at'] = None # updated_at is Optional, so None is acceptable
    
    # Format participants as a list of UserSimple Pydantic models
    if 'participants' in room_dict and isinstance(room_dict['participants'], list):
        formatted_participants = []
        for p_id in room_dict['participants']:
            user_data = user_service.get_user_by_anonymous_id(p_id)
            if user_data:
                formatted_participants.append(UserSimple(
                    anonymous_id=uuid.UUID(user_data['anonymous_id']),
                    username=user_data['username'],
                    avatar_url=user_data.get('avatar_url')
                ))
        room_dict['participants'] = formatted_participants
    else:
        room_dict['participants'] = [] # Ensure it's always a list

    # Format last_message if present as a ChatMessageRead Pydantic model
    if 'last_message' in room_dict and room_dict['last_message']:
        room_dict['last_message'] = _format_chat_message(room_dict['last_message'])
    else:
        room_dict['last_message'] = None # Ensure it's None if no last message
    
    return room_dict

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

    # Retrieve the document to get server-generated timestamps and then format
    created_doc = chat_rooms_collection.document(room_id).get()
    if not created_doc.exists:
        raise ValueError("Failed to create chat room")

    return _format_chat_room(created_doc.to_dict())

def get_chat_room(room_id: str) -> Optional[dict]:
    """
    Retrieves a chat room document by its ID.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    doc_ref = chat_rooms_collection.document(room_id)
    doc = doc_ref.get()
    if doc.exists:
        return _format_chat_room(doc.to_dict())
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
        return _format_chat_room(doc.to_dict())
    return None

def get_chat_rooms_for_user(user_id: str, limit: int = 20) -> List[dict]:
    """
    Retrieves a list of chat rooms for a specific user.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    query = chat_rooms_collection.where('participants', 'array_contains', user_id).order_by('updated_at', direction='DESCENDING')
    docs = query.limit(limit).stream()
    return [_format_chat_room(doc.to_dict()) for doc in docs]

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
        "message_id": message_id,
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
    return [_format_chat_message(doc.to_dict()) for doc in docs]

def delete_all_chat_messages_by_user(user_id: str) -> int:
    """
    Deletes all messages sent by a specific user across all chat rooms they are a participant in.
    Updates the 'last_message' field in chat rooms if the deleted message was the last one.
    """
    db = firestore.client()
    chat_rooms_collection = get_chat_rooms_collection()
    deleted_count = 0

    # Get all chat rooms the user is a participant in
    user_chat_rooms = chat_rooms_collection.where('participants', 'array_contains', user_id).stream()

    for room_doc in user_chat_rooms:
        room_ref = room_doc.reference
        messages_query = room_ref.collection('messages').where('sender_id', '==', user_id).stream()
        
        messages_to_delete_refs = []
        for msg_doc in messages_query:
            messages_to_delete_refs.append(msg_doc.reference)
            deleted_count += 1
        
        # Delete messages in batches
        if messages_to_delete_refs:
            batch = db.batch()
            for msg_ref in messages_to_delete_refs:
                batch.delete(msg_ref)
            batch.commit()

        # Check if the last_message was from this user and update if necessary
        room_data = room_doc.to_dict()
        if room_data and room_data.get('last_message') and room_data['last_message'].get('sender_id') == user_id:
            # Find the new last message, if any
            remaining_messages_query = room_ref.collection('messages').order_by('timestamp', direction='DESCENDING').limit(1).stream()
            new_last_message = None
            for msg_doc in remaining_messages_query:
                new_last_message = {
                    "content": msg_doc.get('content'),
                    "sender_id": msg_doc.get('sender_id'),
                    "timestamp": msg_doc.get('timestamp'),
                }
            
            batch = db.batch()
            batch.update(room_ref, {
                'last_message': new_last_message,
                'updated_at': firestore.SERVER_TIMESTAMP # Update timestamp as room content changed
            })
            batch.commit()
            
    return deleted_count