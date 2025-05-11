from sqlalchemy import Column, Integer, String, DateTime, func, Text, Enum as SAEnum, Boolean
from app.db.session import Base
from sqlalchemy.orm import relationship
from app.schemas.enums import ChatAvailabilityEnum

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # For anonymous users, this could be a unique generated ID
    anonymous_id = Column(String, unique=True, index=True, nullable=False)
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
    