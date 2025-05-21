# app/schemas/user_relationship.py
import uuid
from pydantic import BaseModel
from datetime import datetime
from .enums import RelationshipTypeEnum
from .user import UserRead # For displaying user info

class UserRelationshipBase(BaseModel):
    target_anonymous_id: uuid.UUID
    relationship_type: RelationshipTypeEnum

class UserRelationshipCreate(UserRelationshipBase):
    pass

class UserRelationshipRead(BaseModel):
    actor_anonymous_id: uuid.UUID
    target_anonymous_id: uuid.UUID
    relationship_type: RelationshipTypeEnum
    created_at: datetime
    # Optionally include more details about actor/target
    # actor: UserSimple
    # target: UserSimple

    class Config:
        from_attributes = True
