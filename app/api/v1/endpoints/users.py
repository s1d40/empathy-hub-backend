from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.token import Token
from app import schemas
from app.services.firestore_services import user_service, post_service, comment_service, chat_service
from app.core.security import create_access_token
from app.core.config import settings
from datetime import timedelta
import uuid
from app.api.v1.firestore_deps import get_current_active_user_firestore

router = APIRouter()

@router.post("/", response_model=Token, status_code=status.HTTP_201_CREATED)
def create_user_anonymous(user_in: schemas.UserCreate):
    """
    Create new user in Firestore.
    Backend generates anonymous_id.
    Returns an access token.
    """
    try:
        user_data = user_service.create_user(user_in=user_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not user_data:
        raise HTTPException(status_code=500, detail="User creation failed unexpectedly.")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data['username'], "anonymous_id": user_data['anonymous_id']},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user_data['username'],
        "anonymous_id": user_data['anonymous_id']
    }

@router.get("/me", response_model=schemas.UserRead)
def read_user_me(current_user: dict = Depends(get_current_active_user_firestore)):
    """
    Get current authenticated user's details from Firestore.
    """
    return current_user

@router.get("/", response_model=List[schemas.UserRead])
def read_users_endpoint(skip: int = 0, limit: int = 100):
    """
    Retrieve users from Firestore.
    """
    users = user_service.get_users(skip=skip, limit=limit)
    return users

@router.get("/anonymous/{user_anonymous_id}", response_model=schemas.UserRead)
def read_user_by_anonymous_id_endpoint(user_anonymous_id: str):
    """
    Get a specific user by their public anonymous ID from Firestore.
    """
    user = user_service.get_user_by_anonymous_id(anonymous_id=user_anonymous_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/me", response_model=schemas.UserRead)
def update_user_me(user_in: schemas.UserUpdate, current_user: dict = Depends(get_current_active_user_firestore)):
    """
    Update current authenticated user's profile in Firestore.
    """
    try:
        updated_user = user_service.update_user(anonymous_id=current_user['anonymous_id'], user_in=user_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_me(current_user: dict = Depends(get_current_active_user_firestore)):
    """
    Delete the current authenticated user's profile from Firestore.
    """
    # TODO: In a real application, this should trigger a process to delete all user's content.
    # For now, it just deletes the user document.
    success = user_service.delete_user(anonymous_id=current_user['anonymous_id'])
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return

@router.delete("/me/chat-messages", response_model=schemas.DeletionSummary, status_code=status.HTTP_200_OK)
def delete_all_my_chat_messages(current_user: dict = Depends(get_current_active_user_firestore)):
    deleted_count = chat_service.delete_all_chat_messages_by_user(user_id=current_user['anonymous_id'])
    return schemas.DeletionSummary(message="All your chat messages have been deleted.", deleted_count=deleted_count)

@router.delete("/me/posts", response_model=schemas.DeletionSummary, status_code=status.HTTP_200_OK)
def delete_all_my_posts(current_user: dict = Depends(get_current_active_user_firestore)):
    deleted_count = post_service.delete_all_posts_by_author(author_id=current_user['anonymous_id'])
    return schemas.DeletionSummary(message="All your posts have been deleted.", deleted_count=deleted_count)

@router.delete("/me/comments", response_model=schemas.DeletionSummary, status_code=status.HTTP_200_OK)
def delete_all_my_comments(current_user: dict = Depends(get_current_active_user_firestore)):
    deleted_count = comment_service.delete_all_comments_by_author(author_id=current_user['anonymous_id'])
    return schemas.DeletionSummary(message="All your comments have been deleted.", deleted_count=deleted_count)

@router.get("/{user_anonymous_id}/posts", response_model=List[schemas.PostRead])
def read_posts_by_user(
    user_anonymous_id: str,
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve posts by a specific user ID from Firestore.
    """
    posts = post_service.get_posts_by_author(author_id=user_anonymous_id)
    # Apply skip and limit manually as get_posts_by_author doesn't support it directly
    return posts[skip : skip + limit]

@router.get("/{user_anonymous_id}/comments", response_model=List[schemas.CommentRead])
def read_comments_by_user(
    user_anonymous_id: str,
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve comments by a specific user ID from Firestore.
    """
    comments = comment_service.get_comments_by_author(author_id=user_anonymous_id)
    # Apply skip and limit manually as get_comments_by_author doesn't support it directly
    return comments[skip : skip + limit]