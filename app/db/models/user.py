from sqlalchemy import Column, Integer, String, DateTime, func, Text, Enum as SAEnum, Boolean
from app.db.session import Base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.schemas.enums import ChatAvailabilityEnum
import uuid

class User(Base):
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
    