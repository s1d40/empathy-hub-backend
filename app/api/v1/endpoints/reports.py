import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.crud import report as crud_report
from app import crud, schemas
from app.db import models
from app.api.v1 import deps
from app.schemas.enums import ReportStatusEnum, ReportedItemTypeEnum

router = APIRouter()

@router.post(
    "/",
    response_model=schemas.ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new report"
)
def submit_report(
    *,
    db: Session = Depends(deps.get_db),
    report_in: schemas.ReportCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """
    Allows an authenticated user to submit a report about a user, post, or comment.
    """
    # Basic validation: Ensure the reported item exists (optional, can be complex)
    # For simplicity, we'll assume the frontend provides valid IDs.
    # More robust validation would check if reported_item_anonymous_id corresponds
    # to an actual User, Post, or Comment based on reported_item_type.

    # Prevent self-reporting if item type is USER
    if report_in.reported_item_type == ReportedItemTypeEnum.USER and report_in.reported_item_anonymous_id == current_user.anonymous_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot report yourself."
        )

    report = crud_report.create_report(db=db, reporter=current_user, obj_in=report_in)
    return report


# --- Admin Endpoints ---
# TODO: Implement proper admin role check for these endpoints.

@router.get(
    "/admin/",
    response_model=List[schemas.ReportRead],
    summary="List all reports (Admin)",
    dependencies=[Depends(deps.get_current_active_user)] # Placeholder for admin check
)
def list_reports_admin(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ReportStatusEnum] = Query(None, alias="status"),
    # current_admin: models.User = Depends(deps.get_current_admin_user) # TODO
):
    """
    (Admin) Retrieves a list of reports, optionally filtered by status.
    """
    reports = crud.report.get_multi_reports_admin(
        db, skip=skip, limit=limit, status=status_filter
    )
    return reports


@router.get(
    "/admin/{report_anonymous_id}",
    response_model=schemas.ReportRead,
    summary="Get a specific report (Admin)",
    dependencies=[Depends(deps.get_current_active_user)] # Placeholder for admin check
)
def get_report_admin(
    report_anonymous_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    # current_admin: models.User = Depends(deps.get_current_admin_user) # TODO
):
    """
    (Admin) Retrieves details for a specific report.
    """
    report = crud.report.get_by_anonymous_id_with_reporter(db, anonymous_report_id=report_anonymous_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.put(
    "/admin/{report_anonymous_id}",
    response_model=schemas.ReportRead,
    summary="Update a report's status (Admin)",
    dependencies=[Depends(deps.get_current_active_user)] # Placeholder for admin check
)
def update_report_admin(
    report_anonymous_id: uuid.UUID,
    report_update_in: schemas.ReportUpdate,
    db: Session = Depends(deps.get_db),
    # current_admin: models.User = Depends(deps.get_current_admin_user) # TODO
):
    """
    (Admin) Updates the status and admin notes for a report.
    Sets `reviewed_at` automatically when status changes.
    """
    report_db = crud.report.get_by_anonymous_id_with_reporter(db, anonymous_report_id=report_anonymous_id)
    if not report_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    updated_report = crud.report.update_report_admin(
        db=db, db_obj=report_db, obj_in=report_update_in
    )
    return updated_report