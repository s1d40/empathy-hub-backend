from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid # Keep uuid for type hinting path parameters
from typing import List
from app import crud
from app.schemas import PostCreate, PostRead, PostUpdate, PostVoteCreate, CommentCreate, CommentRead, CommentUpdate, CommentVoteCreate
from app.db.session import get_db
from app.db.models.user import User # For current_user dependency
from app.api.v1.deps import get_current_active_user # Import the real dependency

router = APIRouter()

@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(
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
def vote_on_post(
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
def read_posts(
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
    posts = crud.crud_post.get_multi_posts(db, skip=skip, limit=limit)
    return posts

@router.get("/{post_anonymous_id}", response_model=PostRead)
def read_post_by_anonymous_id(
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
def update_post(
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
def delete_post(
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


# --- Comment Endpoints ---

@router.post(
    "/{post_anonymous_id}/comments/",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment for a post"
)
def create_comment_for_post(
    post_anonymous_id: uuid.UUID,
    comment_in: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new comment for a specific post.
    The user making the comment will be the currently authenticated user.
    """
    post = crud.crud_post.get_post_by_anonymous_id(db, anonymous_post_id=post_anonymous_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Use the instance of CRUDComment from crud.comment
    comment = crud.comment.create_with_author_and_post(
        db=db, obj_in=comment_in, author_id=current_user.anonymous_id, post_id=post.anonymous_post_id
    )
    return comment

@router.get(
    "/{post_anonymous_id}/comments/",
    response_model=List[CommentRead],
    summary="List comments for a post"
)
def read_comments_for_post(
    post_anonymous_id: uuid.UUID,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
    # current_user: User = Depends(get_current_active_user), # Only if comments are private
):
    """
    Retrieve comments for a specific post with pagination.
    """
    post = crud.crud_post.get_post_by_anonymous_id(db, anonymous_post_id=post_anonymous_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    comments = crud.comment.get_multi_by_post(db, post_id=post.anonymous_post_id, skip=skip, limit=limit)
    return comments

@router.put(
    "/comments/{comment_id}/", # Operating directly on comment_id
    response_model=CommentRead,
    summary="Update a comment"
)
def update_comment(
    comment_id: uuid.UUID, # This refers to Comment.anonymous_comment_id (exposed as 'id')
    comment_in: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
    "/comments/{comment_id}/", # Operating directly on comment_id
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment"
)
def delete_comment(
    comment_id: uuid.UUID, # This refers to Comment.anonymous_comment_id (exposed as 'id')
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
    return # Returns 204 No Content on success

@router.post(
    "/comments/{comment_anonymous_id}/vote", # Path using the comment's anonymous_id
    response_model=CommentRead, # Return the updated comment
    summary="Vote on a comment"
)
def vote_on_comment(
    *,
    db: Session = Depends(get_db),
    comment_anonymous_id: uuid.UUID, # Get the comment's anonymous ID from the path
    vote_in: CommentVoteCreate, # Get the vote type from the request body
    current_user: User = Depends(get_current_active_user) # Ensure user is authenticated
):
    """
    Vote on a comment (upvote or downvote).
    Sending the same vote again will unvote.
    Sending a different vote will change the vote.
    """
    # The get_current_active_user dependency already handles authentication check

    updated_comment = crud.comment.process_comment_vote(
        db=db, comment_anonymous_id=comment_anonymous_id, user_anonymous_id=current_user.anonymous_id, requested_vote_type=vote_in.vote_type
    )
    if not updated_comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return updated_comment