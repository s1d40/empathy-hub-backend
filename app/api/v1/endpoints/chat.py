import uuid
from typing import List, Union, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from app import schemas
from app.services.firestore_services import chat_service, chat_request_service, user_service, user_relationship_service
from app.api.v1.firestore_deps import get_current_active_user_firestore
from app.schemas.enums import ChatAvailabilityEnum, ChatRequestStatusEnum, RelationshipTypeEnum
from app.core.chat_manager import manager # This manager might need refactoring for a stateless environment
from app.core import security

router = APIRouter()

@router.post(
    "/initiate-direct",
    response_model=Union[schemas.ChatRoomRead, schemas.ChatRequestRead],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a 1-on-1 chat or send a chat request"
)
def initiate_direct_chat_or_request(
    chat_initiate_in: schemas.ChatInitiate,
    current_user: dict = Depends(get_current_active_user_firestore),
) -> Any:
    if current_user['anonymous_id'] == str(chat_initiate_in.target_user_anonymous_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot initiate a chat with yourself.")

    target_user = user_service.get_user_by_anonymous_id(str(chat_initiate_in.target_user_anonymous_id))
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    actor_blocks_target = user_relationship_service.get_relationship(current_user['anonymous_id'], target_user['anonymous_id'], RelationshipTypeEnum.BLOCK)
    target_blocks_actor = user_relationship_service.get_relationship(target_user['anonymous_id'], current_user['anonymous_id'], RelationshipTypeEnum.BLOCK)
    if actor_blocks_target or target_blocks_actor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot initiate chat due to an existing block.")

    if target_user['chat_availability'] == ChatAvailabilityEnum.DO_NOT_DISTURB:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This user is not accepting chat messages or requests.")
    
    elif target_user['chat_availability'] == ChatAvailabilityEnum.REQUEST_ONLY:
        chat_request_in = schemas.ChatRequestCreate(
            requestee_anonymous_id=target_user['anonymous_id'],
            initial_message=chat_initiate_in.initial_message
        )
        chat_request = chat_request_service.create_chat_request(request_in=chat_request_in, requester_id=current_user['anonymous_id'])
        return chat_request
    
    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[target_user['anonymous_id']],
        is_group=False
    )
    chat_room = chat_service.create_chat_room(room_in=room_create_schema, initiator_id=current_user['anonymous_id'])
    return chat_room

@router.get("/", response_model=List[schemas.ChatRoomRead], summary="List chat rooms for the current user")
def list_user_chat_rooms(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_rooms = chat_service.get_chat_rooms_for_user(user_id=current_user['anonymous_id'], limit=limit)
    return chat_rooms

@router.get("/requests/pending", response_model=List[schemas.ChatRequestRead], summary="List pending chat requests")
def list_pending_chat_requests(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user_firestore),
):
    pending_requests = chat_request_service.get_pending_requests_for_user(user_id=current_user['anonymous_id'], limit=limit)
    return pending_requests

@router.post("/requests/{request_id}/accept", response_model=schemas.ChatRoomRead, summary="Accept a chat request")
def accept_chat_request(
    request_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_request = chat_request_service.get_chat_request(request_id)
    if not chat_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if chat_request['requestee_id'] != current_user['anonymous_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to respond to this request.")
    if chat_request['status'] != ChatRequestStatusEnum.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat request is no longer pending.")

    chat_request_service.update_request_status(request_id, status=ChatRequestStatusEnum.ACCEPTED)
    
    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[chat_request['requester_id']],
        is_group=False
    )
    new_chat_room = chat_service.create_chat_room(room_in=room_create_schema, initiator_id=current_user['anonymous_id'])
    return new_chat_room

@router.post("/requests/{request_id}/decline", response_model=schemas.ChatRequestRead, summary="Decline a chat request")
def decline_chat_request(
    request_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_request = chat_request_service.get_chat_request(request_id)
    if not chat_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if chat_request['requestee_id'] != current_user['anonymous_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to respond to this request.")
    if chat_request['status'] != ChatRequestStatusEnum.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat request is no longer pending.")

    updated_request = chat_request_service.update_request_status(request_id, status=ChatRequestStatusEnum.DECLINED)
    return updated_request

@router.get("/{room_id}/messages", response_model=List[schemas.ChatMessageRead], summary="Get message history")
def get_chat_room_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_room = chat_service.get_chat_room(room_id)
    if not chat_room or current_user['anonymous_id'] not in chat_room['participants']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a participant of this chat room.")

    messages = chat_service.get_messages_for_chat_room(room_id=room_id, limit=limit)
    return messages

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
    # Authenticate user from token
    try:
        payload = security.decode_access_token(token_data=token)
        user_id = payload.get("anonymous_id")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication credentials")
            return
        current_user = user_service.get_user_by_anonymous_id(user_id)
        if not current_user or not current_user.get("is_active"):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found or inactive")
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication credentials")
        return

    # Authorize user for the chat room
    chat_room = chat_service.get_chat_room(room_id)
    if not chat_room or current_user['anonymous_id'] not in chat_room['participants']:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Chat room not found or you are not a participant")
        return

    # TODO: Add block check for 1-on-1 chats

    await manager.connect(websocket, room_id, current_user['anonymous_id'])
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = schemas.WebSocketChatMessage.model_validate_json(data)
                
                # Save message to Firestore
                db_message = chat_service.add_message_to_chat_room(
                    room_id=room_id,
                    message_in=schemas.ChatMessageCreate(content=message_data.content),
                    sender_id=current_user['anonymous_id']
                )
                
                # TODO: The manager needs to be refactored to not require a db session
                # and to handle dictionary objects.
                # For now, we'll just broadcast the dictionary.
                await manager.broadcast_to_room_dict(room_id, db_message, current_user['anonymous_id'])

            except Exception as e:
                await manager.send_personal_message(websocket, f"Error: {str(e)}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, current_user['anonymous_id'])