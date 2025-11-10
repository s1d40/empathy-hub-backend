from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
import uuid
# from app.db.session import Base

class Comment:
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(PG_UUID(as_uuid=True), unique=True, index=True, default=uuid.uuid4)
    post_id = Column(PG_UUID(as_uuid=True), ForeignKey("posts.post_id"), nullable=False)
    author_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)

    author = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    votes = relationship("CommentVoteLog", back_populates="comment", cascade="all, delete-orphan")