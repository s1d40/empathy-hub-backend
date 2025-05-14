import enum
from sqlalchemy import Column, Integer, ForeignKey, Enum as SAEnum, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from .post_vote_log import VoteTypeEnum # Reusing the existing VoteTypeEnum

class CommentVoteLog(Base):
    __tablename__ = "comment_vote_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    comment_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("comments.anonymous_comment_id"), nullable=False)
    # Explicitly set create_type=False for this shared enum.
    # The enum type 'votetypeenum_sqlalchemy' is expected to be created
    # by the first model that uses it (e.g., PostVoteLog).
    vote_type = Column(
        SAEnum(VoteTypeEnum, name="comment_vote_enum_type", create_type=False),
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="comment_votes")
    comment = relationship("Comment", back_populates="votes_log")

    __table_args__ = (UniqueConstraint('user_anonymous_id', 'comment_anonymous_id', name='uq_user_comment_vote_uc'),)