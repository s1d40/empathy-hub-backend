import uuid
from sqlalchemy import Column, Integer, String, DateTime, func, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.session import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    anonymous_post_id = Column(PG_UUID(as_uuid=True), unique=True, index=True, default=uuid.uuid4)

    title = Column(String, nullable=True, index=True)
    content = Column(Text, nullable=False)
    author_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False) # We'll add Topic model later

    is_active = Column(Boolean, default=True, nullable=False) # For moderation or soft deletes
    is_edited = Column(Boolean, default=False, nullable=False) # To indicate if a post has been edited

    upvotes = Column(Integer, default=0, nullable=False)
    downvotes = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    author = relationship("User", back_populates="posts")
    votes_log = relationship("PostVoteLog", back_populates="post", cascade="all, delete-orphan")
    # topic = relationship("Topic", back_populates="posts") # We'll add Topic model later
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan") # For when we add Comments

    # TODO: Add relationship for comments when Comment model is created
    # TODO: Add relationship for topic when Topic model is created