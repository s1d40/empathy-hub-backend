import uuid
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from app.db.models.report import Report
from app.db.models.user import User
from app.schemas.report import ReportCreate, ReportUpdate
from app.schemas.enums import ReportStatusEnum, ReportedItemTypeEnum
from sqlalchemy import func # For func.now()
from app.crud.base import CRUDBase


class CRUDReport(CRUDBase[Report, ReportCreate, ReportUpdate]):
    def create_report(self, db: Session, *, reporter: User, obj_in: ReportCreate) -> Report:
        # Basic check for duplicate active reports by the same user for the same item
        existing_report = db.query(Report).filter(
            Report.reporter_anonymous_id == reporter.anonymous_id,
            Report.reported_item_anonymous_id == obj_in.reported_item_anonymous_id,
            Report.reported_item_type == obj_in.reported_item_type,
            Report.status == ReportStatusEnum.PENDING
        ).first()
        if existing_report:
            return existing_report # Or raise an error, or update the existing one

        db_obj = Report(
            reporter_anonymous_id=reporter.anonymous_id,
            reported_item_type=obj_in.reported_item_type,
            reported_item_anonymous_id=obj_in.reported_item_anonymous_id,
            reason=obj_in.reason,
            status=ReportStatusEnum.PENDING # Default status
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        # Eager load reporter for the response
        db.refresh(db_obj, attribute_names=['reporter'])
        return db_obj

    def get_by_anonymous_id_with_reporter(self, db: Session, *, anonymous_report_id: uuid.UUID) -> Optional[Report]:
        return db.query(Report).options(
            joinedload(Report.reporter)
        ).filter(Report.anonymous_report_id == anonymous_report_id).first()

    def get_multi_reports_admin(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ReportStatusEnum] = None
    ) -> List[Report]:
        query = db.query(self.model).options(joinedload(self.model.reporter))
        if status:
            query = query.filter(self.model.status == status)
        return query.order_by(self.model.created_at.desc()).offset(skip).limit(limit).all()

    def update_report_admin(
        self,
        db: Session,
        *,
        db_obj: Report,
        obj_in: Union[ReportUpdate, Dict[str, Any]]
    ) -> Report:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        # If status is being changed (and not to PENDING), set reviewed_at
        if "status" in update_data and update_data["status"] != ReportStatusEnum.PENDING:
            db_obj.reviewed_at = func.now()
        
        # Apply other updates from obj_in
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        return super().update(db, db_obj=db_obj, obj_in=update_data) # Use super's update for commit/refresh

report = CRUDReport(Report)