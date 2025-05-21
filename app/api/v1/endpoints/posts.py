from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid # Keep uuid for type hinting path parameters
from typing import List
from app import crud
from app.schemas import PostCreate, PostRead, PostUpdate, PostVoteCreate # Removed Comment schemas
from app.db.session import get_db
from app.db.models.user import User # For current_user dependency
from app.api.v1.deps import get_current_active_user # Import the real dependency

router = APIRouter()

@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post( # Added tags for OpenAPI
    *,
    db: Session = Depends(get_db),
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create new post.
    """
    if not current_user: # This check might be redundant if get_current_active_user handles it
         raise HTTPException(status_code=403, detail="Not authenticated")
    post = crud.crud_post.create_post(db=db, post_in=post_in, author_anonymous_id=current_user.anonymous_id)
    return post

@router.post("/{post_anonymous_id}/vote", response_model=PostRead)
def vote_on_post( # Added tags for OpenAPI
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    vote_in: PostVoteCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Vote on a post (upvote or downvote).
    Sending the same vote again will unvote.
    Sending a different vote will change the vote.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    post_db_obj = crud.crud_post.get_post_by_anonymous_id(db=db, anonymous_post_id=post_anonymous_id)
    if not post_db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    updated_post = crud.crud_post.process_post_vote(
        db=db, post_id=post_db_obj.id, user_anonymous_id=current_user.anonymous_id, requested_vote_type=vote_in.vote_type
    )
    if not updated_post: # Should not happen if post_db_obj was found, but good practice
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not process vote")
    return updated_post

# TODO: Add endpoints for GET /posts/, GET /posts/{id}, PUT /posts/{id}, DELETE /posts/{id}
@router.get("/", response_model=List[PostRead])
def read_posts( # Added tags for OpenAPI
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a list of posts.
    Requires authentication, but does not filter by user unless
    the CRUD operation itself is modified to do so.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")
    posts = crud.crud_post.get_multi_posts(
        db,
        skip=skip,
        limit=limit,
        current_user_anonymous_id=current_user.anonymous_id
    )
    return posts

@router.get("/{post_anonymous_id}", response_model=PostRead)
def read_post_by_anonymous_id( # Added tags for OpenAPI
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific post by its anonymous ID.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")
    post = crud.crud_post.get_post_by_anonymous_id(db=db, anonymous_post_id=post_anonymous_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post

@router.put("/{post_anonymous_id}", response_model=PostRead)
def update_post( # Added tags for OpenAPI
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    post_in: PostUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a post.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")

    db_post = crud.crud_post.get_post_by_anonymous_id(
        db=db, anonymous_post_id=post_anonymous_id
    )
    if not db_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    if db_post.author_anonymous_id != current_user.anonymous_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post",
        )
    updated_post = crud.crud_post.update_post(db=db, db_post=db_post, post_in=post_in)
    return updated_post

@router.delete("/{post_anonymous_id}", response_model=PostRead)
def delete_post( # Added tags for OpenAPI
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a post. Only the author of the post can delete it.
    """
    if not current_user: # This check is technically redundant if get_current_active_user raises on its own
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

    db_post_to_delete = crud.crud_post.get_post_by_anonymous_id(db=db, anonymous_post_id=post_anonymous_id)
    if not db_post_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if db_post_to_delete.author_anonymous_id != current_user.anonymous_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this post")

    # Create a representation of the object before deleting for the response
    # This ensures all relationships are loaded if PostRead expects them
    deleted_post_representation = PostRead.model_validate(db_post_to_delete)
    crud.crud_post.delete_post(db=db, post_id=db_post_to_delete.id)
    return deleted_post_representation