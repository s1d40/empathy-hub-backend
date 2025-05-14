import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Text, func, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.session import Base

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    # Use anonymous_comment_id as the primary key internally for consistency
    anonymous_comment_id = Column(PG_UUID(as_uuid=True),  default=uuid.uuid4, unique=True, index=True, nullable=False)
    content = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    upvotes = Column(Integer, default=0, nullable=False)
    downvotes = Column(Integer, default=0, nullable=False)

    post_id = Column(PG_UUID(as_uuid=True), ForeignKey("posts.anonymous_post_id"), nullable=False)
    author_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)

    # Relationships
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")
    votes_log = relationship("CommentVoteLog", back_populates="comment", cascade="all, delete-orphan")



    # If you want 'id' to be an alias for anonymous_comment_id in the model layer too (optional)
    # @property
    # def id(self):
    #     return self.anonymous_comment_id