import enum
from sqlalchemy import Column, Integer, ForeignKey, Enum as SAEnum, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base

class VoteTypeEnum(str, enum.Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"

class PostVoteLog(Base):
    __tablename__ = "post_vote_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    vote_type = Column(SAEnum(VoteTypeEnum, name="votetypeenum_sqlalchemy"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships (optional, but can be useful for querying if needed)
    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes_log")

    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='_user_post_vote_uc'),)