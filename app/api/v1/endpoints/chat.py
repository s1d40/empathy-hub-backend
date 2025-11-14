import uuid
import logging
from typing import List, Union, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from app import schemas
from app.services.firestore_services import chat_service, chat_request_service, user_service, user_relationship_service, notification_service
from app.api.v1.firestore_deps import get_current_active_user_firestore
from app.schemas.enums import ChatAvailabilityEnum, ChatRequestStatusEnum, RelationshipTypeEnum, NotificationTypeEnum
from app.core.chat_manager import manager
from app.core import security
from app.core.utils import convert_uuids_to_str

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post(
    "/initiate-direct",
    response_model=Union[schemas.ChatRoomRead, schemas.ChatRequestReadWithNewFlag],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a 1-on-1 chat or send a chat request"
)
async def initiate_direct_chat_or_request(
    chat_initiate_in: schemas.ChatInitiate,
    current_user: dict = Depends(get_current_active_user_firestore),
) -> Any:
    if current_user['anonymous_id'] == str(chat_initiate_in.target_user_anonymous_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot initiate a chat with yourself.")

    target_user = user_service.get_user_by_anonymous_id(str(chat_initiate_in.target_user_anonymous_id))
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    # --- NEW: Check for existing direct chat room first ---
    existing_chat_room = chat_service.get_direct_chat_by_participants(
        user1_id=current_user['anonymous_id'],
        user2_id=target_user['anonymous_id']
    )
    if existing_chat_room:
        if chat_initiate_in.initial_message:
            # Add the initial message to the existing chat room
            await chat_service.add_message_to_chat_room(
                room_id=existing_chat_room['anonymous_room_id'],
                message_in=schemas.ChatMessageCreate(content=chat_initiate_in.initial_message),
                sender_id=current_user['anonymous_id']
            )
        return existing_chat_room
    # --- END NEW ---

    actor_blocks_target = user_relationship_service.get_relationship(current_user['anonymous_id'], target_user['anonymous_id'], RelationshipTypeEnum.BLOCK)
    target_blocks_actor = user_relationship_service.get_relationship(target_user['anonymous_id'], current_user['anonymous_id'], RelationshipTypeEnum.BLOCK)
    if actor_blocks_target or target_blocks_actor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot initiate chat due to an existing block.")

    if target_user['chat_availability'] == ChatAvailabilityEnum.DO_NOT_DISTURB:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This user is not accepting chat messages or requests.")
    
    elif target_user['chat_availability'] == ChatAvailabilityEnum.REQUEST_ONLY:
        # --- MODIFIED: Check for existing pending request specifically from current_user to target_user ---
        existing_request = chat_request_service.get_pending_request_from_to(
            requester_id=current_user['anonymous_id'],
            requestee_id=target_user['anonymous_id']
        )
        
        if existing_request:
            # If a pending request already exists from current_user to target_user, return it.
            # Frontend can then display "Request Already Sent" or similar.
            # We also need to indicate that this is an existing request, not a new one.
            existing_request['is_new_request'] = False
            return existing_request
        # --- END MODIFIED ---

        chat_request_in = schemas.ChatRequestCreate(
            requestee_anonymous_id=target_user['anonymous_id'],
            initial_message=chat_initiate_in.initial_message
        )
        chat_request = chat_request_service.create_chat_request(request_in=chat_request_in, requester_id=current_user['anonymous_id'])
        
        notification_service.create_notification(
            notification_in=schemas.notification.NotificationCreate(
                recipient_id=uuid.UUID(target_user['anonymous_id']),
                sender_id=uuid.UUID(current_user['anonymous_id']),
                notification_type=NotificationTypeEnum.CHAT_REQUEST_RECEIVED,
                content=f"User {current_user['username']} has sent you a chat request.",
                resource_id=chat_request['anonymous_request_id'],
            )
        )
        
        # This is a newly created request
        chat_request['is_new_request'] = True
        return chat_request
    
    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[target_user['anonymous_id']],
        is_group=False
    )
    new_chat_room = chat_service.create_chat_room(room_in=room_create_schema, initiator_id=current_user['anonymous_id'])
    
    serializable_chat_room = convert_uuids_to_str(new_chat_room)
    participant_ids = [str(p.anonymous_id) for p in new_chat_room['participants']]
    await manager.publish_chat_room_update_to_pubsub(serializable_chat_room, participant_ids)
    
    return new_chat_room

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
async def accept_chat_request(
    request_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_request = chat_request_service.get_chat_request(request_id)
    if not chat_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if str(chat_request['requestee_anonymous_id']) != current_user['anonymous_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to respond to this request.")
    if chat_request['status'] != ChatRequestStatusEnum.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat request is no longer pending.")

    chat_request_service.update_request_status(request_id, status=ChatRequestStatusEnum.ACCEPTED)
    
    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[str(chat_request['requester_anonymous_id'])],
        is_group=False
    )
    new_chat_room = chat_service.create_chat_room(
        room_in=room_create_schema, 
        initiator_id=current_user['anonymous_id'],
        initial_message=chat_request.get('initial_message'),
        requester_id=str(chat_request['requester_anonymous_id'])
    )
    
    serializable_chat_room = convert_uuids_to_str(new_chat_room)
    participant_ids = [str(p.anonymous_id) for p in new_chat_room['participants']]
    await manager.publish_chat_room_update_to_pubsub(serializable_chat_room, participant_ids)
    
    return new_chat_room

@router.post("/requests/{request_id}/decline", response_model=schemas.ChatRequestRead, summary="Decline a chat request")
def decline_chat_request(
    request_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_request = chat_request_service.get_chat_request(request_id)
    if not chat_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if str(chat_request['requestee_anonymous_id']) != current_user['anonymous_id']:
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
    if not chat_room or not any(str(p.anonymous_id) == current_user['anonymous_id'] for p in chat_room['participants']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a participant of this chat room.")

    messages = chat_service.get_messages_for_chat_room(room_id=room_id, limit=limit)
    return messages

@router.post("/{room_id}/mark-read", response_model=schemas.ChatRoomRead, summary="Mark a chat room as read for the current user")
def mark_chat_room_as_read_endpoint(
    room_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    success = chat_service.mark_chat_room_as_read(room_id=room_id, user_id=current_user['anonymous_id'])
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to mark chat room as read or room not found/user not participant.")
    
    updated_chat_room = chat_service.get_chat_room(room_id)
    if not updated_chat_room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat room not found after update.")
    return updated_chat_room

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
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

    chat_room = chat_service.get_chat_room(room_id)
    if not chat_room or not any(str(p.anonymous_id) == current_user['anonymous_id'] for p in chat_room['participants']):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Chat room not found or you are not a participant")
        return

    await manager.connect_chat(websocket, room_id, current_user['anonymous_id'])
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = schemas.WebSocketChatMessage.model_validate_json(data)
                
                db_message = chat_service.add_message_to_chat_room(
                    room_id=room_id,
                    message_in=schemas.ChatMessageCreate(content=message_data.content),
                    sender_id=current_user['anonymous_id'],
                    client_message_id=message_data.client_message_id
                )
                
                serializable_db_message = convert_uuids_to_str(db_message)
                participant_ids = [str(p.anonymous_id) for p in chat_room['participants']]
                await manager.publish_chat_message_to_pubsub(room_id, serializable_db_message, participant_ids)

            except Exception as e:
                error_payload = {"detail": f"Error processing message: {str(e)}"}
                if 'message_data' in locals() and message_data.client_message_id:
                    error_payload["clientMessageId"] = str(message_data.client_message_id)
                error_message = schemas.WebSocketMessage(type="error", payload=error_payload).model_dump_json()
                await manager.send_personal_message(websocket, error_message)
    except WebSocketDisconnect:
        manager.disconnect_chat(websocket, room_id, current_user['anonymous_id'])
    except Exception:
        manager.disconnect_chat(websocket, room_id, current_user['anonymous_id'])

@router.websocket("/ws-updates")
async def websocket_chat_updates_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
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

    await manager.connect_chat_updates(websocket, current_user['anonymous_id'])
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect_chat_updates(current_user['anonymous_id'])
    except Exception:
        manager.disconnect_chat_updates(current_user['anonymous_id'])

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
async def accept_chat_request(
    request_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_request = chat_request_service.get_chat_request(request_id)
    if not chat_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if str(chat_request['requestee_anonymous_id']) != current_user['anonymous_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to respond to this request.")
    if chat_request['status'] != ChatRequestStatusEnum.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat request is no longer pending.")

    chat_request_service.update_request_status(request_id, status=ChatRequestStatusEnum.ACCEPTED)
    
    room_create_schema = schemas.ChatRoomCreate(
        participant_anonymous_ids=[str(chat_request['requester_anonymous_id'])],
        is_group=False
    )
    new_chat_room = chat_service.create_chat_room(
        room_in=room_create_schema, 
        initiator_id=current_user['anonymous_id'],
        initial_message=chat_request.get('initial_message'),
        requester_id=str(chat_request['requester_anonymous_id'])
    )
    
    serializable_chat_room = convert_uuids_to_str(new_chat_room)
    participant_ids = [str(p.anonymous_id) for p in new_chat_room['participants']]
    await manager.publish_chat_room_update_to_pubsub(serializable_chat_room, participant_ids)
    
    return new_chat_room

@router.post("/requests/{request_id}/decline", response_model=schemas.ChatRequestRead, summary="Decline a chat request")
def decline_chat_request(
    request_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    chat_request = chat_request_service.get_chat_request(request_id)
    if not chat_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat request not found.")
    if str(chat_request['requestee_anonymous_id']) != current_user['anonymous_id']:
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
    if not chat_room or not any(str(p.anonymous_id) == current_user['anonymous_id'] for p in chat_room['participants']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a participant of this chat room.")

    messages = chat_service.get_messages_for_chat_room(room_id=room_id, limit=limit)
    return messages

@router.post("/{room_id}/mark-read", response_model=schemas.ChatRoomRead, summary="Mark a chat room as read for the current user")
def mark_chat_room_as_read_endpoint(
    room_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    success = chat_service.mark_chat_room_as_read(room_id=room_id, user_id=current_user['anonymous_id'])
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to mark chat room as read or room not found/user not participant.")
    
    updated_chat_room = chat_service.get_chat_room(room_id)
    if not updated_chat_room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat room not found after update.")
    return updated_chat_room

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
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

    chat_room = chat_service.get_chat_room(room_id)
    if not chat_room or not any(str(p.anonymous_id) == current_user['anonymous_id'] for p in chat_room['participants']):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Chat room not found or you are not a participant")
        return

    await manager.connect_chat(websocket, room_id, current_user['anonymous_id'])
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = schemas.WebSocketChatMessage.model_validate_json(data)
                
                db_message = chat_service.add_message_to_chat_room(
                    room_id=room_id,
                    message_in=schemas.ChatMessageCreate(content=message_data.content),
                    sender_id=current_user['anonymous_id'],
                    client_message_id=message_data.client_message_id
                )
                
                serializable_db_message = convert_uuids_to_str(db_message)
                participant_ids = [str(p.anonymous_id) for p in chat_room['participants']]
                await manager.publish_chat_message_to_pubsub(room_id, serializable_db_message, participant_ids)

            except Exception as e:
                error_payload = {"detail": f"Error processing message: {str(e)}"}
                if 'message_data' in locals() and message_data.client_message_id:
                    error_payload["clientMessageId"] = str(message_data.client_message_id)
                error_message = schemas.WebSocketMessage(type="error", payload=error_payload).model_dump_json()
                await manager.send_personal_message(websocket, error_message)
    except WebSocketDisconnect:
        manager.disconnect_chat(websocket, room_id, current_user['anonymous_id'])
    except Exception:
        manager.disconnect_chat(websocket, room_id, current_user['anonymous_id'])

@router.websocket("/ws-updates")
async def websocket_chat_updates_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
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

    await manager.connect_chat_updates(websocket, current_user['anonymous_id'])
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect_chat_updates(current_user['anonymous_id'])
    except Exception:
        manager.disconnect_chat_updates(current_user['anonymous_id'])
