import uuid
from firebase_admin import firestore
from google.cloud.firestore_v1.transforms import Sentinel
from pydantic import BaseModel
from datetime import datetime

def convert_uuids_to_str(data):
    """
    Recursively converts special objects in a data structure to JSON-serializable types.
    Handles: UUID, datetime, Pydantic models.
    Omits: Firestore Sentinels.
    """
    if isinstance(data, dict):
        return {k: convert_uuids_to_str(v) for k, v in data.items() if not isinstance(v, Sentinel)}
    elif isinstance(data, list):
        # Filter out sentinels from lists as well
        return [convert_uuids_to_str(elem) for elem in data if not isinstance(elem, Sentinel)]
    elif isinstance(data, uuid.UUID):
        return str(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, BaseModel):
        # model_dump(mode='json') handles nested datetimes and UUIDs within the model
        return data.model_dump(mode='json')
    elif isinstance(data, Sentinel):
        # This case is for sentinels that might appear outside of dict values (e.g., in a list)
        return None
    return data
