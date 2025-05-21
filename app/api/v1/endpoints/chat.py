import uuid
from typing import List, Union, Any
# import logging # Using print for direct debugging

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import models
from app.api.v1 import deps
from app.schemas.enums import ChatAvailabilityEnum, ChatRequestStatusEnum, RelationshipTypeEnum
from app.core.chat_manager import manager # Import the connection manager
from app.core import security # For decoding JWT token

router = APIRouter()
# Get a logger instance (e.g., uvicorn's error logger, or your app's logger)
# logger = logging.getLogger("uvicorn.error")


@router.post(
    "/initiate-direct",
    response_model=Union[schemas.ChatRoomRead, schemas.ChatRequestRead],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a 1-on-1 chat or send a chat request"
)
def initiate_direct_chat_or_request(
    *,
    db: Session = Depends(deps.get_db), # This was missing the db dependency
    chat_initiate_in: schemas.ChatInitiate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any: # Using Any because Union response_model handling can be tricky with status codes
    """
    Initiates a direct (1-on-1) chat with another user or sends a chat request
    if the target user's chat availability is 'request_only'.

    - If target user is 'open_to_chat':
        - Checks for an existing direct chat room.
        - If exists, returns the existing room (HTTP 200).
        - If not, creates a new chat room and returns it (HTTP 201).
    - If target user is 'request_only':
        - Creates a new chat request and returns it (HTTP 201).
    - If target user is 'do_not_disturb':
        - Returns an error (HTTP 403).
    """
    if current_user.anonymous_id == chat_initiate_in.target_user_anonymous_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot initiate a chat with yourself.",
        )

    # Reverted to use crud.crud_user as per project structure
    target_user = crud.crud_user.get_user_by_anonymous_id(db, anonymous_id=chat_initiate_in.target_user_anonymous_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found.",
        )

    # --- Block Check ---
    # Check if current_user has blocked target_user
    actor_blocks_target = crud.user_relationship.get_relationship(
        db,
        actor_anonymous_id=current_user.anonymous_id,
        target_anonymous_id=target_user.anonymous_id,
        relationship_type=RelationshipTypeEnum.BLOCK
    )
    # Check if target_user has blocked current_user
    target_blocks_actor = crud.user_relationship.get_relationship(
        db,
        actor_anonymous_id=target_user.anonymous_id,
        target_anonymous_id=current_user.anonymous_id,
        relationship_type=RelationshipTypeEnum.BLOCK
    )
    if actor_blocks_target or target_blocks_actor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot initiate chat due to an existing block.")
    # --- End Block Check ---

    if target_user.chat_availability == ChatAvailabilityEnum.DO_NOT_DISTURB:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user is not accepting chat messages or requests at this time.",
        )
    elif target_user.chat_availability == ChatAvailabilityEnum.REQUEST_ONLY:
        chat_request_in = schemas.ChatRequestCreate(
            requestee_anonymous_id=target_user.anonymous_id,
            initial_message=chat_initiate_in.initial_message
        )
        chat_request = crud.chat_request.create_request(
            db, request_in=chat_request_in, requester_anonymous_id=current_user.anonymous_id
        )
        # For Union response_model, FastAPI might not automatically pick the correct status code
        # if it differs from the main one. We might need to return a Response object directly
        # or adjust how we handle status codes for different outcomes.
        # For now, let's assume 201 is fine for both new request and new room.
        return chat_request
    
    # Else: target_user.chat_availability == ChatAvailabilityEnum.OPEN_TO_CHAT
    # For create_with_participants, participant_users should not include the initiator
    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[target_user.anonymous_id], # Only the other participant
        is_group=False
    )
    chat_room = crud.chat_room.create_with_participants(
        db, room_in=room_create_schema, initiator_user=current_user, participant_users=[target_user]
    )
    return chat_room


@router.get(
    "/",
    response_model=List[schemas.ChatRoomRead],
    summary="List chat rooms for the current user"
)
def list_user_chat_rooms(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> List[schemas.ChatRoomRead]:
    """
    Retrieves a list of chat rooms the current authenticated user is a participant in.
    Includes the last message sent in each room for preview.
    """
    chat_rooms_db = crud.chat_room.get_multi_for_user(
        db, user_anonymous_id=current_user.anonymous_id, skip=skip, limit=limit
    )
    
    chat_rooms_read: List[schemas.ChatRoomRead] = []
    for room_db in chat_rooms_db:
        last_message_read = None
        if room_db.messages:
            # Messages are ordered by timestamp desc in the model relationship,
            # or we can sort them here if not guaranteed by the ORM relationship.
            # Assuming the relationship `order_by="ChatMessage.timestamp.desc()"`
            last_message_db = sorted(room_db.messages, key=lambda m: m.timestamp, reverse=True)[0] if room_db.messages else None
            if last_message_db:
                last_message_read = schemas.ChatMessageRead.model_validate(last_message_db)
        
        # Ensure participants are loaded and converted to UserSimple
        participants_simple = [schemas.UserSimple.model_validate(p) for p in room_db.participants]

        # Construct ChatRoomRead by passing ORM object and then overriding specific fields
        # that were transformed or are not directly on the ORM model in the exact Pydantic shape.
        room_data = room_db.__dict__ # Get a dictionary of the ORM object's attributes
        room_data["last_message"] = last_message_read
        room_data["participants"] = participants_simple
        
        room_read = schemas.ChatRoomRead.model_validate(room_data)
        chat_rooms_read.append(room_read)
        
    return chat_rooms_read


# ... (other imports)
# Ensure you have schemas.ChatRequestRead if not already imported
# from app import schemas

# ... (existing router and endpoints)

@router.get(
    "/requests/pending", # This would map to GET /api/v1/chat/requests/pending
    response_model=List[schemas.ChatRequestRead],
    summary="List pending chat requests for the current user"
)
def list_pending_chat_requests(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> List[schemas.ChatRequestRead]:
    """
    Retrieves a list of pending chat requests where the current user is the requestee.
    """
    # You'll need a CRUD function for this, e.g., in crud.chat_request
    # Assuming crud.chat_request.get_pending_for_user exists or you create it
    pending_requests = crud.chat_request.get_pending_requests_for_user(
        db, user_anonymous_id=current_user.anonymous_id, skip=skip, limit=limit
    )
    return pending_requests


# You would also need to implement crud.chat_request.get_pending_for_user
# This function would query your ChatRequest model for requests where:
# - requestee_anonymous_id == current_user.anonymous_id
# - status == ChatRequestStatusEnum.PENDING (or equivalent)

@router.post(
    "/requests/{request_anonymous_id}/accept",
    response_model=schemas.ChatRoomRead, # Returns the newly created chat room
    status_code=status.HTTP_200_OK, # Or 201 if we consider the room new, but 200 for action on request
    summary="Accept a chat request"
)
def accept_chat_request(
    *,
    db: Session = Depends(deps.get_db),
    request_anonymous_id: uuid.UUID,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> schemas.ChatRoomRead:
    """
    Allows the requestee to accept a pending chat request.
    This will change the request status to ACCEPTED and create a new direct chat room.
    """
    chat_request_db = crud.chat_request.get_by_anonymous_id(db, anonymous_request_id=request_anonymous_id)

    if not chat_request_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")

    if chat_request_db.requestee_anonymous_id != current_user.anonymous_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to respond to this request.")

    if chat_request_db.status != ChatRequestStatusEnum.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Chat request is no longer pending (current status: {chat_request_db.status.value}).")

    # Update chat request status
    crud.chat_request.update_status(db, db_obj=chat_request_db, status=ChatRequestStatusEnum.ACCEPTED)

    # Create a new direct chat room
    # The current_user (requestee) is the initiator of this room creation action.
    # The other participant is the original requester of the chat request.
    requester_user = chat_request_db.requester # Assumes requester is loaded by get_by_anonymous_id
    if not requester_user:
        # This should not happen if DB integrity is maintained and requester was loaded
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Requester details not found for the chat request.")

    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[requester_user.anonymous_id],
        is_group=False
    )
    
    new_chat_room = crud.chat_room.create_with_participants(
        db, room_in=room_create_schema, initiator_user=current_user, participant_users=[requester_user]
    )
    
    # Manually construct ChatRoomRead as create_with_participants returns the ORM model
    # and we might need to ensure all fields for ChatRoomRead are present.
    # However, if create_with_participants returns a fully populated ORM object that
    # Pydantic can validate directly, this manual step might be simplified.
    # For now, let's assume Pydantic can handle it if relationships are loaded.
    
    # Re-fetch the room with all necessary details for ChatRoomRead if create_with_participants doesn't load them all
    # (e.g., last_message which would be None for a new room)
    # For a newly created room, last_message will be None.
    # Participants should be loaded by create_with_participants or by get_by_anonymous_id.
    
    # Let's rely on Pydantic's from_attributes for now.
    # Ensure participants are loaded for the response.
    db.refresh(new_chat_room, attribute_names=['participants'])

    return schemas.ChatRoomRead.model_validate(new_chat_room)

@router.post(
    "/requests/{request_anonymous_id}/decline",
    response_model=schemas.ChatRequestRead,
    summary="Decline a chat request"
)
def decline_chat_request(
    *,
    db: Session = Depends(deps.get_db),
    request_anonymous_id: uuid.UUID,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Allows the requestee to decline a pending chat request.
    This will change the request status to DECLINED.
    """
    chat_request_db = crud.chat_request.get_by_anonymous_id(db, anonymous_request_id=request_anonymous_id)
    if not chat_request_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if chat_request_db.requestee_anonymous_id != current_user.anonymous_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to respond to this request.")
    if chat_request_db.status != ChatRequestStatusEnum.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Chat request is no longer pending (current status: {chat_request_db.status.value}).")

    updated_request = crud.chat_request.update_status(db, db_obj=chat_request_db, status=ChatRequestStatusEnum.DECLINED)
    return updated_request

@router.get(
    "/{room_anonymous_id}/messages",
    response_model=List[schemas.ChatMessageRead],
    summary="Get message history for a chat room"
)
def get_chat_room_messages(
    *,
    db: Session = Depends(deps.get_db),
    room_anonymous_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100), # Default to 50 messages, max 100
    current_user: models.User = Depends(deps.get_current_active_user),
) -> List[schemas.ChatMessageRead]:
    """
    Retrieves the message history for a specific chat room.
    Ensures the current user is a participant of the room.
    Messages are returned newest first.
    """
    chat_room = crud.chat_room.get_by_anonymous_id(db, anonymous_room_id=room_anonymous_id)
    if not chat_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat room not found.",
        )

    # Verify current user is a participant
    if not any(p.anonymous_id == current_user.anonymous_id for p in chat_room.participants):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant of this chat room.",
        )

    messages_db = crud.chat_message.get_multi_for_room(db, chatroom_anonymous_id=room_anonymous_id, skip=skip, limit=limit)
    return [schemas.ChatMessageRead.model_validate(msg) for msg in messages_db]


@router.websocket("/ws/{room_anonymous_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_anonymous_id: uuid.UUID,
    token: str = Query(...), # Expect token as a query parameter
    # db: Session = Depends(deps.get_db) # REMOVE THIS: Depends() for session doesn't work directly in WS signature
):
    # Manually get DB session for WebSockets
    print("--- WS: Attempting to connect ---")
    # This is a common pattern as Depends doesn't work the same way with WebSockets
    db_session_gen = deps.get_db()
    db_for_ws: Session = next(db_session_gen)

    current_user: models.User | None = None
    try:
        print(f"--- WS: Decoding token: {token[:20]}... ---") # Print part of token for brevity
        payload = security.decode_access_token(token_data=token)
        print(f"--- WS: Token payload decoded: {payload} ---")
        if payload and payload.get("sub"): # "sub" usually holds username or user ID
            # Assuming your token's "sub" is username, or you have anonymous_id in token
            user_anonymous_id_from_token_str = payload.get("anonymous_id") # Adjust if your token stores it differently
            print(f"--- WS: anonymous_id from token string: {user_anonymous_id_from_token_str} ---")
            if user_anonymous_id_from_token_str:
                user_anonymous_id_from_token = uuid.UUID(user_anonymous_id_from_token_str)
                print(f"--- WS: Fetching user with anonymous_id: {user_anonymous_id_from_token} ---")
                # Corrected to use crud.crud_user
                current_user = crud.crud_user.get_user_by_anonymous_id(db_for_ws, anonymous_id=user_anonymous_id_from_token)
                print(f"--- WS: Fetched current_user: {'Exists' if current_user else 'None'} ---")
    except Exception as e: # Broad exception for token validation issues
        print(f"--- WS: Exception during token decoding or user fetching: {e} ---")
        current_user = None

    if not current_user:
        print("--- WS: No current_user after token processing, closing connection (Invalid auth) ---")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication credentials")
        return

    print(f"--- WS Auth: current_user.anonymous_id = {current_user.anonymous_id} ---")

    print(f"--- WS Auth: Fetching chat room with anonymous_id: {room_anonymous_id} ---")
    chat_room = crud.chat_room.get_by_anonymous_id(db_for_ws, anonymous_room_id=room_anonymous_id)
    
    if chat_room:
        print(f"--- WS Auth: Found chat_room.anonymous_id = {chat_room.anonymous_room_id} ---")
        participant_ids = [p.anonymous_id for p in chat_room.participants]
        print(f"--- WS Auth: Participant IDs in fetched room: {participant_ids} ---")
        is_participant_check = any(p.anonymous_id == current_user.anonymous_id for p in chat_room.participants)
        print(f"--- WS Auth: Is current_user ({current_user.anonymous_id}) in participants? {is_participant_check} ---")
    else:
        print(f"--- WS Auth: Chat room with anonymous_id {room_anonymous_id} NOT found by CRUD. ---")

    if not chat_room or not any(p.anonymous_id == current_user.anonymous_id for p in chat_room.participants):
        print(f"--- WS: Closing connection (Room not found or current_user not a participant) ---")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Chat room not found or you are not a participant")
        return

    # --- BEGIN BLOCK CHECK FOR 1-ON-1 CHATS AT CONNECTION ---
    if not chat_room.is_group and len(chat_room.participants) == 2:
        other_participant_anonymous_id: uuid.UUID | None = None
        for p_user in chat_room.participants:
            if p_user.anonymous_id != current_user.anonymous_id:
                other_participant_anonymous_id = p_user.anonymous_id
                break
        
        if other_participant_anonymous_id:
            # Check if current_user has blocked the other participant
            actor_blocks_target = crud.user_relationship.get_relationship(
                db_for_ws,
                actor_anonymous_id=current_user.anonymous_id,
                target_anonymous_id=other_participant_anonymous_id,
                relationship_type=RelationshipTypeEnum.BLOCK
            )
            # Check if the other participant has blocked current_user
            target_blocks_actor = crud.user_relationship.get_relationship(
                db_for_ws,
                actor_anonymous_id=other_participant_anonymous_id,
                target_anonymous_id=current_user.anonymous_id,
                relationship_type=RelationshipTypeEnum.BLOCK
            )
            if actor_blocks_target or target_blocks_actor:
                print(f"--- WS: Closing connection due to block between {current_user.anonymous_id} and {other_participant_anonymous_id} ---")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Chat disabled due to a block.")
                return # The main finally block will handle db_session_gen cleanup
    # --- END BLOCK CHECK FOR 1-ON-1 CHATS AT CONNECTION ---

    await manager.connect(websocket, room_anonymous_id, current_user.anonymous_id)
    print(f"--- WS: User {current_user.anonymous_id} connected to room {room_anonymous_id} via ConnectionManager ---")
    # Optional: broadcast user joined message
    # await manager.broadcast_to_room(room_anonymous_id, f"User {current_user.username} joined", current_user.anonymous_id)

    try:
        while True:
            print(f"--- WS ({room_anonymous_id}): Waiting for message from {current_user.anonymous_id} ---")
            data = await websocket.receive_text()
            print(f"--- WS ({room_anonymous_id}): Received raw data: {data} ---")
            try:
                # Assuming client sends JSON parsable to WebSocketChatMessage
                message_data = schemas.WebSocketChatMessage.model_validate_json(data)
                
                # Create and save the message to DB
                db_message = crud.chat_message.create_message(
                    db=db_for_ws,
                    message_in=schemas.ChatMessageCreate(content=message_data.content),
                    chatroom_anonymous_id=room_anonymous_id,
                    sender_anonymous_id=current_user.anonymous_id
                )
                # Convert DB message to Pydantic schema for broadcasting
                message_to_broadcast = schemas.ChatMessageRead.model_validate(db_message)
                print(f"--- WS ({room_anonymous_id}): Broadcasting message_id {message_to_broadcast.anonymous_message_id} ---")
                await manager.broadcast_to_room(db_for_ws, room_anonymous_id, message_to_broadcast, current_user.anonymous_id)

            except Exception as e: # Catch Pydantic validation errors or other issues
                print(f"--- WS ({room_anonymous_id}): Error processing/broadcasting message: {e} ---")
                await manager.send_personal_message(websocket, f"Error processing message: Invalid format. {str(e)}")

    except WebSocketDisconnect:
        print(f"--- WS: User {current_user.anonymous_id} disconnected from room {room_anonymous_id} ---")
        manager.disconnect(websocket, room_anonymous_id, current_user.anonymous_id)
        # Optional: broadcast user left message
        # await manager.broadcast_to_room(room_anonymous_id, f"User {current_user.username} left", current_user.anonymous_id)
    finally:
        print(f"--- WS: Cleaning up for room {room_anonymous_id}, user {current_user.anonymous_id if current_user else 'Unknown'} ---")
        # Ensure db session is closed if get_db uses a try/finally pattern
        try:
            next(db_session_gen) # This would be the 'finally' part of get_db
        except StopIteration:
            pass # Generator finished