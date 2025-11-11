import uuid
from typing import List, Optional
from firebase_admin import firestore
from app.schemas.chat import ChatRoomCreate, ChatMessageCreate, UserSimple, ChatMessageRead
from app.services.firestore_services import user_service
from datetime import datetime

# This service replaces the functionality of crud/crud_chat.py for a Firestore database.

def get_chat_rooms_collection():
    """Returns the 'chat_rooms' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('chat_rooms')

def _format_chat_room(room_dict: dict) -> Optional[dict]:
    """
    Formats a chat room dictionary from Firestore to match the ChatRoomRead schema.
    """
    if not room_dict:
        return None

    # Rename room_id to anonymous_room_id
    room_dict['anonymous_room_id'] = room_dict.pop('room_id')

    # Convert Firestore Timestamps to datetime objects
    if isinstance(room_dict.get('created_at'), firestore.SERVER_TIMESTAMP.__class__):
        # If it's still a Sentinel, it means it hasn't been written/read back yet, or is a placeholder.
        # For now, we'll set it to a default or handle it as None if it's not a real datetime.
        # In a real scenario, you'd re-fetch the document after creation to get actual timestamps.
        room_dict['created_at'] = datetime.now() # Placeholder, should be actual timestamp
    elif isinstance(room_dict.get('created_at'), firestore.Timestamp):
        room_dict['created_at'] = room_dict['created_at'].to_datetime()

    if isinstance(room_dict.get('updated_at'), firestore.SERVER_TIMESTAMP.__class__):
        room_dict['updated_at'] = datetime.now() # Placeholder
    elif isinstance(room_dict.get('updated_at'), firestore.Timestamp):
        room_dict['updated_at'] = room_dict['updated_at'].to_datetime()
    
    # Format participants
    if 'participants' in room_dict and isinstance(room_dict['participants'], list):
        formatted_participants = []
        for p_id in room_dict['participants']:
            user_data = user_service.get_user_by_anonymous_id(p_id)
            if user_data:
                formatted_participants.append(UserSimple(anonymous_id=user_data['anonymous_id'], username=user_data['username']).model_dump())
        room_dict['participants'] = formatted_participants

    # Format last_message if present
    if 'last_message' in room_dict and room_dict['last_message']:
        last_msg = room_dict['last_message']
        # Assuming last_message_summary in Firestore has content, sender_id, timestamp
        # Need to convert sender_id to UserSimple and timestamp to datetime
        sender_id = last_msg.get('sender_id')
        sender_user_simple = None
        if sender_id:
            sender_data = user_service.get_user_by_anonymous_id(sender_id)
            if sender_data:
                sender_user_simple = UserSimple(anonymous_id=sender_data['anonymous_id'], username=sender_data['username'])
        
        if isinstance(last_msg.get('timestamp'), firestore.Timestamp):
            last_msg['timestamp'] = last_msg['timestamp'].to_datetime()
        elif isinstance(last_msg.get('timestamp'), firestore.SERVER_TIMESTAMP.__class__):
            last_msg['timestamp'] = datetime.now() # Placeholder

        room_dict['last_message'] = ChatMessageRead(
            anonymous_message_id=uuid.uuid4(), # This is a placeholder, actual message ID should be used
            chatroom_anonymous_id=room_dict['anonymous_room_id'],
            sender_anonymous_id=uuid.UUID(sender_id) if sender_id else uuid.uuid4(), # Placeholder
            content=last_msg.get('content'),
            timestamp=last_msg.get('timestamp'),
            sender=sender_user_simple
        ).model_dump()
    
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
