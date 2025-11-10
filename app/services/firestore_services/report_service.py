import uuid
from typing import List, Optional
from firebase_admin import firestore
from app.schemas.report import ReportCreate, ReportUpdate
from app.schemas.enums import ReportStatusEnum

# This service replaces the functionality of crud/crud_report.py for a Firestore database.

def get_reports_collection():
    """Returns the 'reports' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('reports')

def create_report(report_in: ReportCreate, reporter_id: str) -> dict:
    """
    Creates a new report document in Firestore.
    """
    reports_collection = get_reports_collection()
    # Check for an existing pending report from the same user for the same item
    existing_query = reports_collection.where('reporter_id', '==', reporter_id) \
                                       .where('reported_item_id', '==', str(report_in.reported_item_anonymous_id)) \
                                       .where('reported_item_type', '==', report_in.reported_item_type.value) \
                                       .where('status', '==', ReportStatusEnum.PENDING.value)
    docs = existing_query.limit(1).stream()
    for doc in docs:
        return doc.to_dict() # Return existing pending report

    report_id = str(uuid.uuid4())
    report_data = {
        "report_id": report_id,
        "reporter_id": reporter_id,
        "reported_item_id": str(report_in.reported_item_anonymous_id),
        "reported_item_type": report_in.reported_item_type.value,
        "reason": report_in.reason,
        "status": ReportStatusEnum.PENDING.value,
        "created_at": firestore.SERVER_TIMESTAMP,
        "reviewed_at": None,
        "admin_notes": None,
    }
    reports_collection.document(report_id).set(report_data)
    return report_data

def get_report(report_id: str) -> Optional[dict]:
    """
    Retrieves a report document by its ID.
    """
    reports_collection = get_reports_collection()
    doc_ref = reports_collection.document(report_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_reports(status: Optional[ReportStatusEnum] = None, limit: int = 100) -> List[dict]:
    """
    Retrieves a list of reports, optionally filtered by status.
    """
    reports_collection = get_reports_collection()
    query = reports_collection
    if status:
        query = query.where('status', '==', status.value)
    
    docs = query.order_by('created_at', direction='DESCENDING').limit(limit).stream()
    return [doc.to_dict() for doc in docs]

def update_report(report_id: str, report_in: ReportUpdate) -> Optional[dict]:
    """
    Updates a report document (typically by an admin).
    """
    reports_collection = get_reports_collection()
    doc_ref = reports_collection.document(report_id)
    doc = doc_ref.get()
    if not doc.exists:
        return None

    update_data = report_in.model_dump(exclude_unset=True)
    
    # If status is being changed, set the reviewed_at timestamp
    if 'status' in update_data and update_data['status'] != ReportStatusEnum.PENDING.value:
        update_data['reviewed_at'] = firestore.SERVER_TIMESTAMP

    doc_ref.update(update_data)
    return doc_ref.get().to_dict()
