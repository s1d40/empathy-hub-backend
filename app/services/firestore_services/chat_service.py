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

def _format_chat_message(message_data: dict, users_map: dict, room_id: str) -> dict:
    """
    Formats a chat message dictionary from Firestore to match the ChatMessageRead schema.
    """
    if not message_data:
        return None

    message_id = message_data.get('message_id')
    sender_id = message_data.get('sender_id')

    formatted_message = {
        'anonymous_message_id': uuid.UUID(message_id) if message_id else None,
        'chatroom_anonymous_id': uuid.UUID(room_id) if room_id else None,
        'sender_anonymous_id': uuid.UUID(sender_id) if sender_id else None,
        'content': message_data.get('content'),
        'timestamp': message_data.get('timestamp'),
        'sender': None
    }

    # Format sender if sender_id exists
    if sender_id:
        sender_data = users_map.get(sender_id)
        if sender_data:
            formatted_message['sender'] = UserSimple(
                anonymous_id=uuid.UUID(sender_data['anonymous_id']),
                username=sender_data['username'],
                avatar_url=sender_data.get('avatar_url')
            )

    return formatted_message

def _format_chat_room(room_dict: dict, users_map: dict) -> Optional[dict]:
    """
    Formats a chat room dictionary from Firestore to match the ChatRoomRead schema.
    """
    if not room_dict:
        return None

    # Ensure room_id is present and convert to UUID
    room_id_str = room_dict.get('room_id')
    if not room_id_str:
        return None # Or raise an error, depending on desired behavior
    
    room_dict['anonymous_room_id'] = uuid.UUID(room_id_str)

    # Convert Firestore Timestamps to datetime objects
    created_at_ts = room_dict.get('created_at')
    if isinstance(created_at_ts, datetime):
        room_dict['created_at'] = created_at_ts
    else:
        room_dict['created_at'] = datetime.now() 

    updated_at_ts = room_dict.get('updated_at')
    if isinstance(updated_at_ts, datetime):
        room_dict['updated_at'] = updated_at_ts
    else:
        room_dict['updated_at'] = None 
    
    # Format participants as a list of UserSimple Pydantic models
    if 'participants' in room_dict and isinstance(room_dict['participants'], list):
        formatted_participants = []
        for p_id in room_dict['participants']:
            user_data = users_map.get(p_id)
            if user_data:
                formatted_participants.append(UserSimple(
                    anonymous_id=uuid.UUID(user_data['anonymous_id']),
                    username=user_data['username'],
                    avatar_url=user_data.get('avatar_url')
                ))
        room_dict['participants'] = formatted_participants
    else:
        room_dict['participants'] = []

    # Format last_message if present as a ChatMessageRead Pydantic model
    if 'last_message' in room_dict and room_dict['last_message']:
        room_dict['last_message'] = _format_chat_message(room_dict['last_message'], users_map, room_id_str)
    else:
        room_dict['last_message'] = None
    
    return room_dict

def create_chat_room(room_in: ChatRoomCreate, initiator_id: str) -> dict:
    """
    Creates a new chat room document in Firestore.
    """
    db = firestore.client()
    chat_rooms_collection = get_chat_rooms_collection()
    
    all_participant_ids = sorted(list(set([initiator_id] + [str(p_id) for p_id in room_in.participant_anonymous_ids])))

    if not room_in.is_group and len(all_participant_ids) != 2:
        raise ValueError("Direct chats must have exactly two participants.")

    @firestore.transactional
    def create_room_in_transaction(transaction):
        if not room_in.is_group:
            # Check if a room with these participants already exists
            query = chat_rooms_collection.where('is_group', '==', False).where('participants', '==', all_participant_ids)
            docs = list(query.stream(transaction=transaction))
            if docs:
                return docs[0].reference

        room_id = str(uuid.uuid4())
        room_ref = chat_rooms_collection.document(room_id)
        room_data = {
            "room_id": room_id,
            "name": room_in.name if room_in.is_group else None,
            "is_group": room_in.is_group,
            "participants": all_participant_ids,
            "last_message": None,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        transaction.set(room_ref, room_data)
        return room_ref

    try:
        transaction = db.transaction()
        room_ref = create_room_in_transaction(transaction)
        created_doc = room_ref.get()
        if not created_doc.exists:
            raise ValueError("Failed to create or find chat room")
        
        # Fetch users for formatting
        user_ids = created_doc.to_dict().get('participants', [])
        users_data = user_service.get_users_by_anonymous_ids(user_ids)
        users_map = {user['anonymous_id']: user for user in users_data}

        return _format_chat_room(created_doc.to_dict(), users_map)
    except Exception as e:
        # Log the exception e
        raise e

def get_chat_room(room_id: str) -> Optional[dict]:
    """
    Retrieves a chat room document by its ID.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    doc_ref = chat_rooms_collection.document(room_id)
    doc = doc_ref.get()
    if doc.exists:
        room_data = doc.to_dict()
        user_ids = room_data.get('participants', [])
        if room_data.get('last_message') and room_data['last_message'].get('sender_id'):
            user_ids.append(room_data['last_message']['sender_id'])
        
        users_data = user_service.get_users_by_anonymous_ids(list(set(user_ids)))
        users_map = {user['anonymous_id']: user for user in users_data}
        return _format_chat_room(room_data, users_map)
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
        room_data = doc.to_dict()
        user_ids = room_data.get('participants', [])
        if room_data.get('last_message') and room_data['last_message'].get('sender_id'):
            user_ids.append(room_data['last_message']['sender_id'])
        
        users_data = user_service.get_users_by_anonymous_ids(list(set(user_ids)))
        users_map = {user['anonymous_id']: user for user in users_data}
        return _format_chat_room(room_data, users_map)
    return None

def get_chat_rooms_for_user(user_id: str, limit: int = 20) -> List[dict]:
    """
    Retrieves a list of chat rooms for a specific user.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    query = chat_rooms_collection.where('participants', 'array_contains', user_id).order_by('updated_at', direction='DESCENDING')
    docs = list(query.limit(limit).stream())

    if not docs:
        return []

    # Collect all user IDs from all rooms
    all_user_ids = set()
    for doc in docs:
        room_data = doc.to_dict()
        all_user_ids.update(room_data.get('participants', []))
        if room_data.get('last_message') and room_data['last_message'].get('sender_id'):
            all_user_ids.add(room_data['last_message']['sender_id'])

    # Fetch all users in one batch
    users_data = user_service.get_users_by_anonymous_ids(list(all_user_ids))
    users_map = {user['anonymous_id']: user for user in users_data}

    # Format all rooms with the complete user map
    return [_format_chat_room(doc.to_dict(), users_map) for doc in docs]

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

    # For the response, we need the sender's data
    users_map = {sender_id: sender_data}
    return _format_chat_message(message_data, users_map)

def get_messages_for_chat_room(room_id: str, limit: int = 50) -> List[dict]:
    """
    Retrieves a list of messages for a specific chat room.
    """
    chat_rooms_collection = get_chat_rooms_collection()
    messages_query = chat_rooms_collection.document(room_id).collection('messages').order_by('timestamp', direction='DESCENDING')
    docs = list(messages_query.limit(limit).stream())

    if not docs:
        return []

    # Collect all user IDs from all messages
    all_user_ids = set(doc.to_dict().get('sender_id') for doc in docs if doc.to_dict().get('sender_id'))

    # Fetch all users in one batch
    users_data = user_service.get_users_by_anonymous_ids(list(all_user_ids))
    users_map = {user['anonymous_id']: user for user in users_data}

    return [_format_chat_message(doc.to_dict(), users_map) for doc in docs]

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