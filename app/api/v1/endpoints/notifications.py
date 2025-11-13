import logging # Import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query # Import Query
from app.schemas.notification import NotificationRead # Import NotificationRead directly
from app import schemas # Keep this for other schemas like UserRead
from app.api.v1.deps import get_current_user
from app.services.firestore_services import notification_service, user_service # Import user_service
from app.schemas.enums import NotificationStatusEnum
from app.core.chat_manager import manager # Import the manager
from app.core import security # Import security

router = APIRouter()
logger = logging.getLogger(__name__) # Initialize logger

@router.get("/notifications/", response_model=List[NotificationRead])
def get_user_notifications(
    limit: int = 100,
    status: Optional[NotificationStatusEnum] = None,
    current_user: schemas.UserRead = Depends(get_current_user)
):
    """
    Retrieve notifications for the current user.
    """
    notifications = notification_service.get_notifications_for_user(
        user_id=str(current_user.anonymous_id),
        limit=limit,
        status=status
    )
    return notifications

@router.put("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: str,
    current_user: schemas.UserRead = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    """
    notification = notification_service.mark_notification_as_read(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    # Ensure the notification belongs to the current user before returning
    if str(notification.get("recipient_id")) != str(current_user.anonymous_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this notification"
        )
    return notification

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_notification(
    notification_id: str,
    current_user: schemas.UserRead = Depends(get_current_user)
):
    """
    Delete a specific notification.
    """
    # First, get the notification to check ownership
    notification = notification_service.get_notification_by_id(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    if str(notification.get("recipient_id")) != str(current_user.anonymous_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this notification"
        )

    if not notification_service.delete_notification(notification_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )
    return {"message": "Notification deleted successfully"}

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...), # Use Query for token
):
    """
    WebSocket endpoint for real-time notifications for a specific user.
    """
    logger.info("WebSocket connection attempt for notifications")
    # Authenticate user from token
    try:
        payload = security.decode_access_token(token_data=token)
        user_id = payload.get("anonymous_id")
        if not user_id:
            logger.warning("WebSocket (notification): No user_id found in token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication credentials")
            return
        current_user = user_service.get_user_by_anonymous_id(user_id)
        if not current_user or not current_user.get("is_active"):
            logger.warning(f"WebSocket (notification): User {user_id} not found or inactive")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found or inactive")
            return
        logger.info(f"WebSocket (notification): User {user_id} authenticated")
    except Exception as e:
        logger.error(f"WebSocket (notification) authentication failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication credentials")
        return

    await manager.connect_notification(websocket, str(user_id)) # Pass user_id directly
    try:
        while True:
            # Keep the connection alive, or handle incoming messages if needed
            # For notifications, typically the server sends messages to the client.
            # Client might send a heartbeat or a "mark all read" signal.
            await websocket.receive_text() 
    except WebSocketDisconnect:
        logger.info(f"WebSocket (notification) disconnected for user: {user_id}")
        manager.disconnect_notification(str(user_id))
    except Exception as e:
        logger.error(f"WebSocket (notification) unexpected error for user {user_id}: {e}")
        manager.disconnect_notification(str(user_id))
