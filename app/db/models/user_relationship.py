# app/db/models/user_relationship.py
import enum
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Enum as SAEnum, func, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.session import Base
from app.schemas.enums import RelationshipTypeEnum # We'll define this enum later

class UserRelationship(Base):
    __tablename__ = "user_relationships"

    id = Column(Integer, primary_key=True, index=True)
    actor_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)
    target_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)

    relationship_type = Column(SAEnum(RelationshipTypeEnum, name="relationshiptypeenum_sqlalchemy"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    actor = relationship("User", foreign_keys=[actor_anonymous_id], back_populates="initiated_relationships")
    target = relationship("User", foreign_keys=[target_anonymous_id], back_populates="received_relationships")

    __table_args__ = (
        UniqueConstraint('actor_anonymous_id', 'target_anonymous_id', 'relationship_type', name='uq_actor_target_relationship_type'),
    )
