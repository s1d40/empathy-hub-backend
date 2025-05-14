import uuid
from sqlalchemy import Column, Integer, String, DateTime, func, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship, column_property # Added column_property
from sqlalchemy.dialects.postgresql import UUID as PG_UUID # Keep PG_UUID
from sqlalchemy import select # Added select
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

# Define column_property after Post and Comment classes are known to avoid circular import issues
# This assumes Comment model is defined in '.comment' and accessible.
from .comment import Comment # Import Comment model for use in column_property

Post.comment_count = column_property(
    select(func.count(Comment.id))
    .where(Comment.post_id == Post.anonymous_post_id) # Link Comment.post_id to Post.anonymous_post_id
    .correlate_except(Comment) # Correlate the subquery with the Post table, excluding Comment itself from correlation
    .as_scalar()
)