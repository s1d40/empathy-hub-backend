from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
from datetime import datetime

# Assuming you have a UserRead schema, or we can define a simpler one here
# from .user import UserRead # Or a UserReadSimple
# from .enums import ChatRequestStatusEnum # No longer needed here

# For now, let's define a simple User representation for chat contexts
# to avoid circular dependencies if UserRead is too complex or not yet fully defined for this.
class UserSimple(BaseModel):
    anonymous_id: uuid.UUID
    username: str
    # avatar_url: Optional[str] = None # If you have avatar URLs

    class Config:
        from_attributes = True

# --- ChatMessage Schemas ---

class ChatMessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class ChatMessageCreate(ChatMessageBase):
    # chatroom_anonymous_id will be from path, sender_anonymous_id from current_user
    pass

class ChatMessageRead(ChatMessageBase):
    anonymous_message_id: uuid.UUID
    chatroom_anonymous_id: uuid.UUID
    sender_anonymous_id: uuid.UUID
    timestamp: datetime
    sender: UserSimple # To show who sent the message

    class Config:
        from_attributes = True

# --- ChatRoom Schemas ---

class ChatRoomBase(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    is_group: bool = False

class ChatRoomCreate(BaseModel):
    # For 1-on-1, this would be one ID. For group, multiple.
    # The initiator is the current_user.
    participant_anonymous_ids: List[uuid.UUID] = Field(..., min_length=1)
    is_group: bool = False
    name: Optional[str] = Field(None, max_length=100) # Primarily for group chats

    # Used when a chat is initiated via a ChatRequest
    # originating_request_anonymous_id: Optional[uuid.UUID] = None

class ChatRoomUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    # Potentially add/remove participants for group chats later

class ChatRoomRead(ChatRoomBase):
    anonymous_room_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    participants: List[UserSimple] = []
    last_message: Optional[ChatMessageRead] = None # To show a preview

    class Config:
        from_attributes = True

# Schema for initiating a chat, which might lead to a ChatRequest or direct ChatRoom
class ChatInitiate(BaseModel):
    target_user_anonymous_id: uuid.UUID
    initial_message: Optional[str] = Field(None, max_length=500) # For REQUEST_ONLY scenarios

# Response for chat initiation could be either a ChatRoomRead or ChatRequestRead
# We might need a union type for this in the endpoint, or separate endpoints.
# For now, the endpoint can decide what to return.


# Schema for WebSocket messages
class WebSocketMessage(BaseModel):
    type: str # e.g., "new_message", "error", "user_joined", "user_left", "typing"
    payload: dict # Flexible payload based on type

class WebSocketChatMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)