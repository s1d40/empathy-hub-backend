import uuid
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from .enums import ReportedItemTypeEnum, ReportStatusEnum # Keep this
from .user import AuthorRead # Changed from UserSimple to AuthorRead

class ReportBase(BaseModel):
    reported_item_type: ReportedItemTypeEnum
    reported_item_anonymous_id: uuid.UUID
    reason: str = Field(..., min_length=10, max_length=1000)

class ReportCreate(ReportBase):
    pass

class ReportRead(ReportBase):
    anonymous_report_id: uuid.UUID
    reporter_anonymous_id: uuid.UUID
    status: ReportStatusEnum
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    admin_notes: Optional[str] = None

    reporter: AuthorRead # Changed to AuthorRead

    class Config:
        from_attributes = True

# For admin updates
class ReportUpdate(BaseModel):
    status: ReportStatusEnum
    admin_notes: Optional[str] = None
