from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app import schemas
from app.services.firestore_services import comment_service, post_service
from app.api.v1.firestore_deps import get_current_active_user_firestore, get_optional_current_user_firestore

router = APIRouter()

@router.post(
    "/{post_id}/comments/",
    response_model=schemas.CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment for a post",
    tags=["comments"]
)
def create_comment_for_post(
    post_id: str,
    comment_in: schemas.CommentCreate,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    """
    Create a new comment for a specific post in Firestore.
    """
    try:
        comment = comment_service.create_comment(
            post_id=post_id,
            comment_in=comment_in,
            author_id=current_user['anonymous_id']
        )
        return comment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get(
    "/{post_id}/comments/",
    response_model=List[schemas.CommentRead],
    summary="List comments for a post",
    tags=["comments"]
)
def read_comments_for_post(
    post_id: str,
    skip: int = 0,
    limit: int = 20,
    current_user: Optional[dict] = Depends(get_optional_current_user_firestore),
):
    """
    Retrieve comments for a specific post from Firestore.
    """
    if not post_service.get_post(post_id=post_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    comments = comment_service.get_comments_for_post(post_id=post_id, skip=skip, limit=limit)
    return comments

@router.put(
    "/comments/{comment_id}",
    response_model=schemas.CommentRead,
    summary="Update a comment",
    tags=["comments"]
)
def update_comment(
    comment_id: str,
    comment_in: schemas.CommentUpdate,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    """
    Update an existing comment in Firestore.
    """
    comment = comment_service.get_comment_by_id(comment_id=comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment['author']['anonymous_id'] != current_user['anonymous_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to update this comment")
    
    updated_comment = comment_service.update_comment(comment_id=comment_id, comment_in=comment_in)
    return updated_comment

@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
    tags=["comments"]
)
def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_active_user_firestore),
):
    """
    Delete a comment from Firestore.
    """
    comment = comment_service.get_comment_by_id(comment_id=comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment['author']['anonymous_id'] != current_user['anonymous_id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to delete this comment")
    
    comment_service.delete_comment(comment_id=comment_id)
    return

@router.post(
    "/comments/{comment_id}/vote",
    response_model=schemas.CommentRead,
    summary="Vote on a comment",
    tags=["comments"]
)
def vote_on_comment(
    comment_id: str,
    vote_in: schemas.CommentVoteCreate,
    current_user: dict = Depends(get_current_active_user_firestore)
):
    """
    Vote on a comment in Firestore.
    """
    try:
        updated_comment = comment_service.vote_on_comment(
            comment_id=comment_id,
            user_id=current_user['anonymous_id'],
            vote_type=vote_in.vote_type
        )
        if not updated_comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        return updated_comment
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))