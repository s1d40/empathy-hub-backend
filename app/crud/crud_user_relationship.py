# app/crud/crud_user_relationship.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models.user_relationship import UserRelationship
from app.db.models.user import User
from app.schemas.enums import RelationshipTypeEnum
from app.crud.base import CRUDBase # Assuming you might want to extend it
from app.schemas.user_relationship import UserRelationshipCreate


class CRUDUserRelationship(CRUDBase[UserRelationship, UserRelationshipCreate, UserRelationshipCreate]): # UpdateSchema can be same as Create for now
    def get_relationship(
        self, db: Session, *, actor_anonymous_id: uuid.UUID, target_anonymous_id: uuid.UUID, relationship_type: RelationshipTypeEnum
    ) -> Optional[UserRelationship]:
        return db.query(UserRelationship).filter(
            UserRelationship.actor_anonymous_id == actor_anonymous_id,
            UserRelationship.target_anonymous_id == target_anonymous_id,
            UserRelationship.relationship_type == relationship_type
        ).first()

    def get_any_relationship(
        self, db: Session, *, actor_anonymous_id: uuid.UUID, target_anonymous_id: uuid.UUID
    ) -> Optional[UserRelationship]:
        """Gets any existing mute or block relationship from actor to target."""
        return db.query(UserRelationship).filter(
            UserRelationship.actor_anonymous_id == actor_anonymous_id,
            UserRelationship.target_anonymous_id == target_anonymous_id
        ).first()


    def create_relationship(
        self, db: Session, *, actor: User, target_user_anonymous_id: uuid.UUID, relationship_type: RelationshipTypeEnum
    ) -> UserRelationship:
        # Remove existing relationship if any (e.g. if muting and already blocked, or vice-versa)
        # Or, decide if block overrides mute etc. For now, let's ensure only one type.
        existing_rel = db.query(UserRelationship).filter(
            UserRelationship.actor_anonymous_id == actor.anonymous_id,
            UserRelationship.target_anonymous_id == target_user_anonymous_id
        ).first()
        if existing_rel:
            if existing_rel.relationship_type == relationship_type:
                return existing_rel # Already exists
            db.delete(existing_rel) # Delete old type to replace with new

        db_obj = UserRelationship(
            actor_anonymous_id=actor.anonymous_id,
            target_anonymous_id=target_user_anonymous_id,
            relationship_type=relationship_type
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove_relationship(
        self, db: Session, *, actor_anonymous_id: uuid.UUID, target_anonymous_id: uuid.UUID, relationship_type: RelationshipTypeEnum
    ) -> Optional[UserRelationship]:
        db_obj = self.get_relationship(
            db,
            actor_anonymous_id=actor_anonymous_id,
            target_anonymous_id=target_anonymous_id,
            relationship_type=relationship_type
        )
        if db_obj:
            db.delete(db_obj)
            db.commit()
        return db_obj

    def get_relationships_by_actor(
        self, db: Session, *, actor_anonymous_id: uuid.UUID, relationship_type: Optional[RelationshipTypeEnum] = None, skip: int = 0, limit: int = 100
    ) -> List[UserRelationship]:
        query = db.query(UserRelationship).filter(UserRelationship.actor_anonymous_id == actor_anonymous_id)
        if relationship_type:
            query = query.filter(UserRelationship.relationship_type == relationship_type)
        return query.offset(skip).limit(limit).all()

    def get_target_ids_by_actor_and_type(
        self, db: Session, *, actor_anonymous_id: uuid.UUID, relationship_types: List[RelationshipTypeEnum]
    ) -> List[uuid.UUID]:
        """Returns a list of target_anonymous_ids for given relationship types."""
        return [
            res[0] for res in db.query(UserRelationship.target_anonymous_id).filter(
                UserRelationship.actor_anonymous_id == actor_anonymous_id,
                UserRelationship.relationship_type.in_(relationship_types)
            ).all()
        ]

user_relationship = CRUDUserRelationship(UserRelationship)
