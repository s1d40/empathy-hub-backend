from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app import schemas
from app.services.firestore_services import post_service
from app.api.v1.firestore_deps import get_current_active_user_firestore

router = APIRouter()

@router.post("/", response_model=schemas.PostRead, status_code=status.HTTP_201_CREATED)
def create_post(
    post_in: schemas.PostCreate,
    current_user: dict = Depends(get_current_active_user_firestore)
):
    """
    Create new post in Firestore.
    """
    try:
        post = post_service.create_post(post_in=post_in, author_id=current_user['anonymous_id'])
        return post
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{post_id}/vote", response_model=schemas.PostRead)
def vote_on_post(
    post_id: str,
    vote_in: schemas.PostVoteCreate,
    current_user: dict = Depends(get_current_active_user_firestore)
):
    """
    Vote on a post in Firestore.
    """
    try:
        updated_post = post_service.vote_on_post(
            post_id=post_id,
            user_id=current_user['anonymous_id'],
            vote_type=vote_in.vote_type
        )
        if not updated_post:
            raise HTTPException(status_code=404, detail="Post not found")
        return updated_post
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/", response_model=List[schemas.PostRead])
def read_posts(skip: int = 0, limit: int = 100):
    """
    Retrieve a list of posts from Firestore.
    """
    posts = post_service.get_posts(skip=skip, limit=limit)
    return posts

@router.get("/{post_id}", response_model=schemas.PostRead)
def read_post_by_id(post_id: str):
    """
    Get a specific post by its ID from Firestore.
    """
    post = post_service.get_post(post_id=post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.put("/{post_id}", response_model=schemas.PostRead)
def update_post(
    post_id: str,
    post_in: schemas.PostUpdate,
    current_user: dict = Depends(get_current_active_user_firestore)
):
    """
    Update a post in Firestore.
    """
    post = post_service.get_post(post_id=post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post['author_id'] != current_user['anonymous_id']:
        raise HTTPException(status_code=403, detail="Not authorized to update this post")

    updated_post = post_service.update_post(post_id=post_id, post_in=post_in)
    return updated_post

@router.delete("/{post_id}", response_model=schemas.PostRead)
def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_active_user_firestore)
):
    """
    Delete a post from Firestore.
    """
    post = post_service.get_post(post_id=post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post['author_id'] != current_user['anonymous_id']:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    # The service returns a boolean, but we return the post data before deletion
    post_service.delete_post(post_id=post_id)
    return post