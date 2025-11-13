from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid
from app.schemas.enums import NotificationTypeEnum, NotificationStatusEnum

class NotificationBase(BaseModel):
    recipient_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None # The user who triggered the notification (e.g., commented)
    notification_type: NotificationTypeEnum
    content: str
    resource_id: uuid.UUID # ID of the resource related to the notification (e.g., post_id, comment_id, chat_room_id)
    status: NotificationStatusEnum = NotificationStatusEnum.UNREAD

class NotificationCreate(NotificationBase):
    pass

class NotificationRead(NotificationBase):
    notification_id: uuid.UUID # Changed from anonymous_notification_id
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
