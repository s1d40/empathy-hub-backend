from sqlalchemy import Column, Integer, ForeignKey, Enum as SAEnum, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.schemas.enums import VoteTypeEnum


class PostVoteLog(Base):
    __tablename__ = "post_vote_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    post_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("posts.anonymous_post_id"), nullable=False)
    vote_type = Column(SAEnum(VoteTypeEnum, name="votetypeenum_sqlalchemy"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships (optional, but can be useful for querying if needed)
    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes_log")

    __table_args__ = (UniqueConstraint('user_anonymous_id', 'post_anonymous_id', name='uq_user_post_vote_uc'),)