from typing import List, Optional
from firebase_admin import firestore
from app.schemas.enums import RelationshipTypeEnum

# This service replaces the functionality of crud/crud_user_relationship.py for a Firestore database.

def get_relationships_collection():
    """Returns the 'user_relationships' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('user_relationships')

def create_relationship(actor_id: str, target_id: str, relationship_type: RelationshipTypeEnum) -> dict:
    """
    Creates a new relationship document (e.g., mute, block).
    The document ID is a composite key to ensure uniqueness.
    """
    relationships_collection = get_relationships_collection()
    if actor_id == target_id:
        raise ValueError("Cannot create a relationship with oneself.")

    # A composite key ensures that there's only one relationship of a certain type from an actor to a target.
    # However, Firestore document IDs cannot contain slashes. A simple concatenation is better.
    doc_id = f"{actor_id}_{relationship_type.value}_{target_id}"
    doc_ref = relationships_collection.document(doc_id)

    # Check if an inverse relationship exists (e.g., if blocking, check if already blocked by target)
    # This logic might be better placed in the API endpoint layer depending on requirements.

    relationship_data = {
        "actor_id": actor_id,
        "target_id": target_id,
        "relationship_type": relationship_type.value,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    doc_ref.set(relationship_data)
    return relationship_data

def get_relationship(actor_id: str, target_id: str, relationship_type: RelationshipTypeEnum) -> Optional[dict]:
    """
    Retrieves a specific relationship document.
    """
    relationships_collection = get_relationships_collection()
    doc_id = f"{actor_id}_{relationship_type.value}_{target_id}"
    doc_ref = relationships_collection.document(doc_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def remove_relationship(actor_id: str, target_id: str, relationship_type: RelationshipTypeEnum) -> bool:
    """
    Deletes a relationship document.
    """
    relationships_collection = get_relationships_collection()
    doc_id = f"{actor_id}_{relationship_type.value}_{target_id}"
    doc_ref = relationships_collection.document(doc_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        return True
    return False

def get_relationships_by_actor(actor_id: str, relationship_type: RelationshipTypeEnum, limit: int = 100) -> List[dict]:
    """
    Retrieves all relationships initiated by a specific actor of a certain type.
    """
    relationships_collection = get_relationships_collection()
    query = relationships_collection.where('actor_id', '==', actor_id) \
                                    .where('relationship_type', '==', relationship_type.value) \
                                    .order_by('created_at', direction='DESCENDING')
    docs = query.limit(limit).stream()
    return [doc.to_dict() for doc in docs]

def get_blocked_user_ids(user_id: str) -> List[str]:
    """
    Gets a list of user IDs that the specified user has blocked.
    """
    blocked_relationships = get_relationships_by_actor(user_id, RelationshipTypeEnum.BLOCK)
    return [rel['target_id'] for rel in blocked_relationships]
