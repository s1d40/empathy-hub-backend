from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app import schemas
from app.services.firestore_services import report_service
from app.api.v1.firestore_deps import get_current_active_user_firestore
from app.schemas.enums import ReportStatusEnum, ReportedItemTypeEnum

router = APIRouter()

# TODO: Create a dependency for checking admin privileges.
def get_current_admin_user(current_user: dict = Depends(get_current_active_user_firestore)):
    # In a real app, you'd check a role field, e.g., if current_user.get('role') != 'admin'
    # For now, we'll just check if the user is active.
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

@router.post(
    "/",
    response_model=schemas.ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new report"
)
def submit_report(
    report_in: schemas.ReportCreate,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    """
    Allows an authenticated user to submit a report about a user, post, or comment.
    """
    if report_in.reported_item_type == ReportedItemTypeEnum.USER and str(report_in.reported_item_anonymous_id) == current_user['anonymous_id']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot report yourself."
        )

    report = report_service.create_report(report_in=report_in, reporter_id=current_user['anonymous_id'])
    return report

# --- Admin Endpoints ---

@router.get(
    "/admin/",
    response_model=List[schemas.ReportRead],
    summary="List all reports (Admin)",
    dependencies=[Depends(get_current_admin_user)]
)
def list_reports_admin(
    status_filter: Optional[ReportStatusEnum] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    (Admin) Retrieves a list of reports, optionally filtered by status.
    """
    reports = report_service.get_reports(status=status_filter, limit=limit)
    return reports

@router.get(
    "/admin/{report_id}",
    response_model=schemas.ReportRead,
    summary="Get a specific report (Admin)",
    dependencies=[Depends(get_current_admin_user)]
)
def get_report_admin(report_id: str):
    """
    (Admin) Retrieves details for a specific report.
    """
    report = report_service.get_report(report_id=report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report

@router.put(
    "/admin/{report_id}",
    response_model=schemas.ReportRead,
    summary="Update a report's status (Admin)",
    dependencies=[Depends(get_current_admin_user)]
)
def update_report_admin(
    report_id: str,
    report_update_in: schemas.ReportUpdate,
):
    """
    (Admin) Updates the status and admin notes for a report.
    """
    report = report_service.get_report(report_id=report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    updated_report = report_service.update_report(report_id=report_id, report_in=report_update_in)
    return updated_report