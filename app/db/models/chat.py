from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
import uuid
# from app.db.session import Base

# Association table for ChatRoom and User
chatroom_participants = Table(
    'chatroom_participants',
    Base.metadata,
    Column('chatroom_id', PG_UUID(as_uuid=True), ForeignKey('chat_rooms.id')),
    Column('user_anonymous_id', PG_UUID(as_uuid=True), ForeignKey('users.anonymous_id'))
)

class ChatRoom:
    __tablename__ = "chat_rooms"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    participants = relationship(
        "User",
        secondary=chatroom_participants,
        back_populates="chat_rooms"
    )
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")

class ChatMessage:
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(PG_UUID(as_uuid=True), ForeignKey('chat_rooms.id'), nullable=False)
    sender_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey('users.anonymous_id'), nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User", back_populates="sent_chat_messages")

class ChatRequest:
    __tablename__ = "chat_requests"
    id = Column(Integer, primary_key=True, index=True)
    requester_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey('users.anonymous_id'), nullable=False)
    requestee_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey('users.anonymous_id'), nullable=False)
    message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requester = relationship("User", foreign_keys=[requester_anonymous_id], back_populates="sent_chat_requests")
    requestee = relationship("User", foreign_keys=[requestee_anonymous_id], back_populates="received_chat_requests")

