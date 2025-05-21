from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from typing import List, Optional

from app import crud
from app.schemas import CommentCreate, CommentRead, CommentUpdate, CommentVoteCreate
from app.db.session import get_db
from app.db.models.user import User # For type hinting current_user
from app.api.v1 import deps # Changed to import deps directly

router = APIRouter()

@router.post(
    "/{post_anonymous_id}/comments/", # This path implies it's nested under a post
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment for a post",
    tags=["comments"] # Add a tag for better OpenAPI docs
)
def create_comment_for_post(
    post_anonymous_id: uuid.UUID,
    comment_in: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Create a new comment for a specific post.
    The user making the comment will be the currently authenticated user.
    """
    post = crud.crud_post.get_post_by_anonymous_id(db, anonymous_post_id=post_anonymous_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found to comment on")
    
    comment = crud.comment.create_with_author_and_post(
        db=db, obj_in=comment_in, author_id=current_user.anonymous_id, post_id=post.anonymous_post_id
    )
    return comment

@router.get(
    "/{post_anonymous_id}/comments/", # This path implies it's nested under a post
    response_model=List[CommentRead],
    summary="List comments for a post",
    tags=["comments"]
)
def read_comments_for_post(
    post_anonymous_id: uuid.UUID,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
    current_user: Optional[User] = Depends(deps.get_optional_current_user),
):
    """
    Retrieve comments for a specific post with pagination.
    """
    post = crud.crud_post.get_post_by_anonymous_id(db, anonymous_post_id=post_anonymous_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found to list comments for")
    
    user_anon_id_for_filtering = current_user.anonymous_id if current_user else None
    
    comments = crud.comment.get_multi_by_post(
        db,
        post_id=post.anonymous_post_id,
        skip=skip, limit=limit,
        current_user_anonymous_id=user_anon_id_for_filtering
    )
    return comments

@router.put(
    "/comments/{comment_id}/", # Path for operating directly on a comment
    response_model=CommentRead,
    summary="Update a comment",
    tags=["comments"]
)
def update_comment(
    comment_id: uuid.UUID,
    comment_in: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Update an existing comment. Only the author of the comment can update it.
    """
    comment = crud.comment.get(db, id=comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.author_id != current_user.anonymous_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to update this comment")
    
    updated_comment = crud.comment.update(db=db, db_obj=comment, obj_in=comment_in)
    return updated_comment

@router.delete(
    "/comments/{comment_id}/", # Path for operating directly on a comment
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
    tags=["comments"]
)
def delete_comment(
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Delete a comment. Only the author of the comment can delete it.
    """
    comment = crud.comment.get(db, id=comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.author_id != current_user.anonymous_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to delete this comment")
    
    crud.comment.remove(db=db, id=comment_id)
    return

@router.post(
    "/comments/{comment_anonymous_id}/vote",
    response_model=CommentRead,
    summary="Vote on a comment",
    tags=["comments"]
)
def vote_on_comment(
    *,
    db: Session = Depends(get_db),
    comment_anonymous_id: uuid.UUID,
    vote_in: CommentVoteCreate,
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Vote on a comment (upvote or downvote).
    """
    updated_comment = crud.comment.process_comment_vote(
        db=db, comment_anonymous_id=comment_anonymous_id, user_anonymous_id=current_user.anonymous_id, requested_vote_type=vote_in.vote_type
    )
    if not updated_comment: # This also implicitly checks if comment was found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found or vote processing failed")
    return updated_comment