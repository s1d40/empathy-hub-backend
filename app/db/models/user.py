from sqlalchemy import Column, Integer, String, DateTime, func, Text, Enum as SAEnum, Boolean
# from app.db.session import Base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.schemas.enums import ChatAvailabilityEnum
import uuid

class User:
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # For anonymous users, this could be a unique generated ID
    anonymous_id = Column(PG_UUID(as_uuid=True), unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True) # Nullable initially
    bio = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)
    chat_availability = Column(
        SAEnum(ChatAvailabilityEnum),
        default=ChatAvailabilityEnum.OPEN_TO_CHAT,
        nullable=False
    )
    pronouns = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan") 
    votes = relationship("PostVoteLog", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    comment_votes = relationship("CommentVoteLog", back_populates="user", cascade="all, delete-orphan")

    # Chat related relationships
    chat_rooms = relationship(
        "ChatRoom",
        secondary="chatroom_participants", # Name of the association table string
        back_populates="participants"
    )
    sent_chat_messages = relationship(
        "ChatMessage",
        back_populates="sender",
        foreign_keys="[ChatMessage.sender_anonymous_id]",
        cascade="all, delete-orphan"
    )
    sent_chat_requests = relationship(
        "ChatRequest",
        back_populates="requester",
        foreign_keys="[ChatRequest.requester_anonymous_id]",
        cascade="all, delete-orphan"
    )
    received_chat_requests = relationship(
        "ChatRequest",
        back_populates="requestee",
        foreign_keys="[ChatRequest.requestee_anonymous_id]",
        cascade="all, delete-orphan"
    )

    # Relationships for Mute/Block
    initiated_relationships = relationship(
        "UserRelationship",
        foreign_keys="[UserRelationship.actor_anonymous_id]",
        back_populates="actor",
        cascade="all, delete-orphan"
    )
    received_relationships = relationship(
        "UserRelationship",
        foreign_keys="[UserRelationship.target_anonymous_id]",
        back_populates="target",
        cascade="all, delete-orphan"
    )

    # Relationship for reports made by this user
    reports_made = relationship(
        "Report",
        foreign_keys="[Report.reporter_anonymous_id]",
        back_populates="reporter",
        cascade="all, delete-orphan")