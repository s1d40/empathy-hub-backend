import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Text, func, Integer, Boolean, Enum as SAEnum, Table, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.session import Base
from app.schemas.enums import ChatRoomTypeEnum, ChatRequestStatusEnum # We'll define these enums in schemas

# Association table for ChatRoom participants (Many-to-Many)
chatroom_participants_association = Table(
    'chatroom_participants', Base.metadata,
    Column('chatroom_id', PG_UUID(as_uuid=True), ForeignKey('chat_rooms.anonymous_room_id'), primary_key=True),
    Column('user_anonymous_id', PG_UUID(as_uuid=True), ForeignKey('users.anonymous_id'), primary_key=True)
)

class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True) # Internal ID
    anonymous_room_id = Column(PG_UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, nullable=False)
    
    name = Column(String(100), nullable=True) # Optional, mainly for group chats
    is_group = Column(Boolean, default=False, nullable=False) # Your suggestion!
    # type = Column(SAEnum(ChatRoomTypeEnum), default=ChatRoomTypeEnum.DIRECT) # Could use is_group or a specific type enum

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) # e.g., when last message sent or participant added

    # Relationships
    messages = relationship("ChatMessage", back_populates="chatroom", cascade="all, delete-orphan", order_by="ChatMessage.timestamp")
    participants = relationship(
        "User",
        secondary=chatroom_participants_association,
        back_populates="chat_rooms"
    )
    # If we have chat requests leading to this room
    # origin_request = relationship("ChatRequest", back_populates="accepted_chat_room")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True) # Internal ID
    anonymous_message_id = Column(PG_UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, nullable=False)
    
    chatroom_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("chat_rooms.anonymous_room_id"), nullable=False)
    sender_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Future: read_status, message_type (text, image, etc.)

    # Relationships
    chatroom = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User", back_populates="sent_chat_messages")


class ChatRequest(Base):
    __tablename__ = "chat_requests"

    id = Column(Integer, primary_key=True, index=True)
    anonymous_request_id = Column(PG_UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, nullable=False)

    requester_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    requestee_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    
    initial_message = Column(Text, nullable=True) # Optional message from requester
    status = Column(SAEnum(ChatRequestStatusEnum), default=ChatRequestStatusEnum.PENDING, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True) # When requestee accepted/declined

    # If accepted, which chat room was created?
    # accepted_chat_room_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("chat_rooms.anonymous_room_id"), nullable=True)

    # Relationships
    requester = relationship("User", foreign_keys=[requester_anonymous_id], back_populates="sent_chat_requests")
    requestee = relationship("User", foreign_keys=[requestee_anonymous_id], back_populates="received_chat_requests")
    # accepted_chat_room = relationship("ChatRoom", back_populates="origin_request")

