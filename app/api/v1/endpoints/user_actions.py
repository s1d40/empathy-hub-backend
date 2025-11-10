from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app import schemas
from app.services.firestore_services import user_relationship_service, user_service
from app.api.v1.firestore_deps import get_current_active_user_firestore
from app.schemas.enums import RelationshipTypeEnum

router = APIRouter()

@router.post(
    "/{target_user_id}/mute",
    response_model=schemas.UserRelationshipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Mute a user"
)
def mute_user(
    target_user_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    if current_user['anonymous_id'] == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot mute yourself.")

    if not user_service.get_user_by_anonymous_id(target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    relationship = user_relationship_service.create_relationship(
        actor_id=current_user['anonymous_id'],
        target_id=target_user_id,
        relationship_type=RelationshipTypeEnum.MUTE
    )
    return relationship

@router.delete(
    "/{target_user_id}/unmute",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unmute a user"
)
def unmute_user(
    target_user_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    user_relationship_service.remove_relationship(
        actor_id=current_user['anonymous_id'],
        target_id=target_user_id,
        relationship_type=RelationshipTypeEnum.MUTE
    )
    return

@router.post(
    "/{target_user_id}/block",
    response_model=schemas.UserRelationshipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Block a user"
)
def block_user(
    target_user_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    if current_user['anonymous_id'] == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself.")

    if not user_service.get_user_by_anonymous_id(target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    relationship = user_relationship_service.create_relationship(
        actor_id=current_user['anonymous_id'],
        target_id=target_user_id,
        relationship_type=RelationshipTypeEnum.BLOCK
    )
    return relationship

@router.delete(
    "/{target_user_id}/unblock",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unblock a user"
)
def unblock_user(
    target_user_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    user_relationship_service.remove_relationship(
        actor_id=current_user['anonymous_id'],
        target_id=target_user_id,
        relationship_type=RelationshipTypeEnum.BLOCK
    )
    return

@router.get(
    "/me/muted",
    response_model=List[schemas.UserSimple],
    summary="List users muted by the current user"
)
def list_muted_users(
    current_user: dict = Depends(get_current_active_user_firestore),
    limit: int = 20
):
    relationships = user_relationship_service.get_relationships_by_actor(
        actor_id=current_user['anonymous_id'],
        relationship_type=RelationshipTypeEnum.MUTE,
        limit=limit
    )
    muted_users = []
    for rel in relationships:
        target_user = user_service.get_user_by_anonymous_id(rel['target_id'])
        if target_user:
             muted_users.append(target_user)
    return muted_users

@router.get(
    "/me/blocked",
    response_model=List[schemas.UserSimple],
    summary="List users blocked by the current user"
)
def list_blocked_users(
    current_user: dict = Depends(get_current_active_user_firestore),
    limit: int = 20
):
    relationships = user_relationship_service.get_relationships_by_actor(
        actor_id=current_user['anonymous_id'],
        relationship_type=RelationshipTypeEnum.BLOCK,
        limit=limit
    )
    blocked_users = []
    for rel in relationships:
        target_user = user_service.get_user_by_anonymous_id(rel['target_id'])
        if target_user:
            blocked_users.append(target_user)
    return blocked_users