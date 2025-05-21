import enum
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Enum as SAEnum, func, Integer, Text, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.db.session import Base
from app.schemas.enums import ReportedItemTypeEnum, ReportStatusEnum # We'll define these

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    anonymous_report_id = Column(PG_UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True, nullable=False)

    reporter_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=False)

    reported_item_type = Column(SAEnum(ReportedItemTypeEnum, name="reporteditemtypeenum_sqlalchemy"), nullable=False)
    # This ID refers to the anonymous_id of the user, post, or comment being reported
    reported_item_anonymous_id = Column(PG_UUID(as_uuid=True), nullable=False) 

    reason = Column(Text, nullable=False)
    status = Column(SAEnum(ReportStatusEnum, name="reportstatusenum_sqlalchemy"), default=ReportStatusEnum.PENDING, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    admin_notes = Column(Text, nullable=True)
    # reviewer_anonymous_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.anonymous_id"), nullable=True) # For admin user

    reporter = relationship("User", foreign_keys=[reporter_anonymous_id], back_populates="reports_made")
    # reviewer = relationship("User", foreign_keys=[reviewer_anonymous_id], back_populates="reports_reviewed")