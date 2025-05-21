from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, desc
from app.db.models.post import Post
from app.db.models.user import User # Needed to access user.anonymous_id
from app.db.models.post_vote_log import PostVoteLog, VoteTypeEnum
from app.schemas.post import PostCreate, PostUpdate
from typing import List, Optional # Keep this
from .crud_user_relationship import user_relationship # For block/mute list
from app.schemas.enums import RelationshipTypeEnum # For block/mute list
import uuid # For type hinting anonymous_post_id

def create_post(db: Session, *, post_in: PostCreate, author_anonymous_id: uuid.UUID) -> Post:
    db_post = Post(
        title=post_in.title,
        content=post_in.content,
        author_anonymous_id=author_anonymous_id
        # anonymous_post_id, is_active, is_edited, created_at, updated_at have defaults or are set by DB
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def get_post(db: Session, post_id: int) -> Optional[Post]:
    # Fetch with author to be consistent for potential PostRead conversion
    return db.execute(
        select(Post)
        .options(joinedload(Post.author))
        .where(Post.id == post_id)
    ).scalar_one_or_none()

def get_post_by_anonymous_id(db: Session, anonymous_post_id: uuid.UUID) -> Optional[Post]:
    return db.execute(
        select(Post)
        .options(joinedload(Post.author)) # Eager load author
        .where(Post.anonymous_post_id == anonymous_post_id)
    ).scalar_one_or_none()

def get_multi_posts(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    current_user_anonymous_id: Optional[uuid.UUID] = None
) -> List[Post]:
    query = select(Post).options(joinedload(Post.author))

    if current_user_anonymous_id:
        excluded_author_ids = user_relationship.get_target_ids_by_actor_and_type(
            db,
            actor_anonymous_id=current_user_anonymous_id,
            relationship_types=[RelationshipTypeEnum.MUTE, RelationshipTypeEnum.BLOCK]
        )
        if excluded_author_ids:
            query = query.filter(Post.author_anonymous_id.notin_(excluded_author_ids))

    query = query.order_by(desc(Post.created_at)).offset(skip).limit(limit)
    return db.execute(query).scalars().all()

def get_multi_posts_by_author_anonymous_id(
    db: Session, *, author_anonymous_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[Post]:
    return db.execute(
        select(Post)
        .options(joinedload(Post.author)) # Eager load author
        .where(Post.author_anonymous_id == author_anonymous_id)
        .order_by(desc(Post.created_at)).offset(skip).limit(limit)
    ).scalars().all()

def update_post(db: Session, *, db_post: Post, post_in: PostUpdate) -> Post:
    update_data = post_in.model_dump(exclude_unset=True)
    if "content" in update_data: # If content is updated, mark as edited
        db_post.is_edited = True

    for field, value in update_data.items():
        setattr(db_post, field, value)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def delete_post(db: Session, post_id: int) -> Optional[Post]:
    db_post = db.get(Post, post_id)
    if db_post:
        db.delete(db_post) # Or set is_active = False for soft delete
        db.commit()
    return db_post

def delete_all_posts_by_author(db: Session, author_anonymous_id: uuid.UUID) -> int:
    """Deletes all posts by a given author and returns the count of deleted posts."""
    posts_to_delete = db.query(Post).filter(Post.author_anonymous_id == author_anonymous_id).all()
    count = len(posts_to_delete)
    if count > 0:
        for post in posts_to_delete:
            db.delete(post)
        db.commit()
    return count


def process_post_vote(db: Session, *, post_id: int, user_anonymous_id: uuid.UUID, requested_vote_type: VoteTypeEnum) -> Optional[Post]:
    # Fetch the post and ensure its author is loaded for potential PostRead conversion
    post = db.execute(
        select(Post)
        .options(joinedload(Post.author))
        .where(Post.id == post_id)
    ).scalar_one_or_none()

    if not post:
        return None # Post not found

    existing_vote_log = db.execute(
        select(PostVoteLog).where(
            PostVoteLog.user_anonymous_id == user_anonymous_id,
            PostVoteLog.post_anonymous_id == post.anonymous_post_id  # Use post's anonymous_id
        )
    ).scalar_one_or_none()

    if existing_vote_log:
        # User has voted on this post before
        if existing_vote_log.vote_type == requested_vote_type:
            # User is clicking the same vote type again - effectively "unvoting"
            db.delete(existing_vote_log)
            if requested_vote_type == VoteTypeEnum.UPVOTE:
                post.upvotes = max(0, post.upvotes - 1)
            else:  # DOWNVOTE
                post.downvotes = max(0, post.downvotes - 1)
        else:
            # User is changing their vote (e.g., from upvote to downvote)
            existing_vote_log.vote_type = requested_vote_type
            if requested_vote_type == VoteTypeEnum.UPVOTE: # Was downvote, now upvote
                post.downvotes = max(0, post.downvotes - 1)
                post.upvotes += 1
            else:  # Was upvote, now downvote
                post.upvotes = max(0, post.upvotes - 1)
                post.downvotes += 1
            db.add(existing_vote_log) # Add to session to save changes to vote_type
    else:
        # New vote for this user on this post
        new_vote_log = PostVoteLog(
            user_anonymous_id=user_anonymous_id,         # Correctly use user_anonymous_id
            post_anonymous_id=post.anonymous_post_id,  # Correctly use post.anonymous_post_id
            vote_type=requested_vote_type
        )
        db.add(new_vote_log)
        if requested_vote_type == VoteTypeEnum.UPVOTE:
            post.upvotes += 1
        else:  # DOWNVOTE
            post.downvotes += 1

    db.add(post) # Add to session to save changes to upvotes/downvotes
    db.commit()
    db.refresh(post) # Refresh to get any DB-side updates and ensure relationships are current
    return post