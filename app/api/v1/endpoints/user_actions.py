import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import models
from app.api.v1 import deps
from app.schemas.enums import RelationshipTypeEnum

router = APIRouter()

@router.post(
    "/{target_user_anonymous_id}/mute",
    response_model=schemas.UserRelationshipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Mute a user"
)
def mute_user(
    target_user_anonymous_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    if current_user.anonymous_id == target_user_anonymous_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot mute yourself.")

    target_user = crud.crud_user.get_user_by_anonymous_id(db, anonymous_id=target_user_anonymous_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    relationship = crud.user_relationship.create_relationship(
        db, actor=current_user, target_user_anonymous_id=target_user_anonymous_id, relationship_type=RelationshipTypeEnum.MUTE
    )
    return relationship

@router.delete(
    "/{target_user_anonymous_id}/unmute",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unmute a user"
)
def unmute_user(
    target_user_anonymous_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    crud.user_relationship.remove_relationship(
        db,
        actor_anonymous_id=current_user.anonymous_id,
        target_anonymous_id=target_user_anonymous_id,
        relationship_type=RelationshipTypeEnum.MUTE
    )
    return

@router.post(
    "/{target_user_anonymous_id}/block",
    response_model=schemas.UserRelationshipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Block a user"
)
def block_user(
    target_user_anonymous_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    if current_user.anonymous_id == target_user_anonymous_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself.")

    target_user = crud.crud_user.get_user_by_anonymous_id(db, anonymous_id=target_user_anonymous_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    # Potentially remove from chat connections, etc.
    relationship = crud.user_relationship.create_relationship(
        db, actor=current_user, target_user_anonymous_id=target_user_anonymous_id, relationship_type=RelationshipTypeEnum.BLOCK
    )
    return relationship

@router.delete(
    "/{target_user_anonymous_id}/unblock",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unblock a user"
)
def unblock_user(
    target_user_anonymous_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    crud.user_relationship.remove_relationship(
        db,
        actor_anonymous_id=current_user.anonymous_id,
        target_anonymous_id=target_user_anonymous_id,
        relationship_type=RelationshipTypeEnum.BLOCK
    )
    return

@router.get(
    "/me/muted",
    response_model=List[schemas.UserSimple], # Or a more detailed schema if needed
    summary="List users muted by the current user"
)
def list_muted_users(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    skip: int = 0,
    limit: int = 20
):
    relationships = crud.user_relationship.get_relationships_by_actor(
        db, actor_anonymous_id=current_user.anonymous_id, relationship_type=RelationshipTypeEnum.MUTE, skip=skip, limit=limit
    )
    muted_users = []
    for rel in relationships:
        target_user = crud.crud_user.get_user_by_anonymous_id(db, anonymous_id=rel.target_anonymous_id)
        if target_user:
             muted_users.append(schemas.UserSimple.model_validate(target_user))
    return muted_users

@router.get(
    "/me/blocked",
    response_model=List[schemas.UserSimple],
    summary="List users blocked by the current user"
)
def list_blocked_users(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
    skip: int = 0,
    limit: int = 20
):
    relationships = crud.user_relationship.get_relationships_by_actor(
        db, actor_anonymous_id=current_user.anonymous_id, relationship_type=RelationshipTypeEnum.BLOCK, skip=skip, limit=limit
    )
    blocked_users = []
    for rel in relationships:
        target_user = crud.crud_user.get_user_by_anonymous_id(db, anonymous_id=rel.target_anonymous_id)
        if target_user:
            blocked_users.append(schemas.UserSimple.model_validate(target_user))
    return blocked_users