from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime

from .enums import ChatRequestStatusEnum
from .chat import UserSimple # UserSimple remains in chat.py for now

# --- ChatRequest Schemas ---

class ChatRequestBase(BaseModel):
    requestee_anonymous_id: uuid.UUID
    initial_message: Optional[str] = Field(None, max_length=500)

class ChatRequestCreate(ChatRequestBase):
    pass

class ChatRequestUpdate(BaseModel):
    status: ChatRequestStatusEnum

class ChatRequestRead(ChatRequestBase):
    anonymous_request_id: uuid.UUID
    requester_anonymous_id: uuid.UUID # Added as it's important to know who sent it
    status: ChatRequestStatusEnum
    created_at: datetime
    responded_at: Optional[datetime] = None

    requester: UserSimple
    requestee: UserSimple

    class Config:
        from_attributes = True