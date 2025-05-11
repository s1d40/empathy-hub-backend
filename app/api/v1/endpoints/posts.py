from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
import shortuuid
from typing import List

from app import crud
from app.schemas.post import PostCreate, PostRead, PostUpdate, PostVoteCreate
from app.db.session import get_db
from app.db.models.user import User # For current_user dependency
from app.db.models.post_vote_log import VoteTypeEnum # For vote_type
# from app.api.v1.deps import get_current_active_user # Placeholder for actual auth

router = APIRouter()

# Placeholder for get_current_active_user dependency
# This would typically come from your authentication setup (e.g., OAuth2 with JWT)
# For now, we'll simulate it or make it optional for basic testing.
# Replace this with your actual dependency once auth is implemented.
async def get_current_active_user_stub(db: Session = Depends(get_db)) -> User:
    # SIMULATION: In a real app, this would verify a token and return the user.
    # For now, let's fetch the first user to simulate an authenticated user.
    # THIS IS NOT SECURE FOR PRODUCTION.
    user = db.query(User).first()
    if not user:
        # If no users, create a dummy one for testing this endpoint
        from app.crud.crud_user import create_user as crud_create_user
        from app.schemas.user import UserCreate as SchemaUserCreate
        
        
        anon_id = shortuuid.ShortUUID().random(length=8)
        user_in = SchemaUserCreate(username=f"TestUser{anon_id}", anonymous_id=str(uuid.uuid4()))
        user = crud_create_user(db=db, user_in=user_in)
        if not user:
            raise HTTPException(status_code=500, detail="Could not create a test user.")
    return user

@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(
    *,
    db: Session = Depends(get_db),
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_user_stub) # Replace with get_current_active_user
):
    """
    Create new post.
    """
    if not current_user:
         raise HTTPException(status_code=403, detail="Not authenticated")
    post = crud.crud_post.create_post(db=db, post_in=post_in, user_id=current_user.id)
    return post

@router.post("/{post_anonymous_id}/vote", response_model=PostRead)
def vote_on_post(
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    vote_in: PostVoteCreate,
    current_user: User = Depends(get_current_active_user_stub) # Replace with get_current_active_user
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
        db=db, post_id=post_db_obj.id, user_id=current_user.id, requested_vote_type=vote_in.vote_type
    )
    if not updated_post: # Should not happen if post_db_obj was found, but good practice
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not process vote")
    return updated_post

# TODO: Add endpoints for GET /posts/, GET /posts/{id}, PUT /posts/{id}, DELETE /posts/{id}
@router.get("/", response_model=List[PostRead])
def read_posts(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user_stub) # Replace with get_current_active_user
):
    """
    Retrieve a list of posts.
    Requires authentication, but does not filter by user unless
    the CRUD operation itself is modified to do so.
    """
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")
    posts = crud.crud_post.get_multi_posts(db, skip=skip, limit=limit)
    return posts

@router.get("/{post_anonymous_id}", response_model=PostRead)
def read_post_by_anonymous_id(
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user_stub) # Replace with get_current_active_user
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
def update_post(
    *,
    db: Session = Depends(get_db),
    post_anonymous_id: uuid.UUID,
    post_in: PostUpdate,
    current_user: User = Depends(get_current_active_user_stub) # Replace with get_current_active_user
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
    if db_post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post",
        )
    updated_post = crud.crud_post.update_post(db=db, db_post=db_post, post_in=post_in)
    return updated_post