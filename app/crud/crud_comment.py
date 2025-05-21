import uuid
from typing import List, Optional, Union, Dict, Any

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, select # For ordering and select

from .base import CRUDBase # Changed to relative import for consistency
from app.db.models.comment import Comment
from app.db.models.comment_vote_log import CommentVoteLog # Import the new model
from app.db.models.post_vote_log import VoteTypeEnum # Reusing VoteTypeEnum
from app.schemas.comment import CommentCreate, CommentUpdate
from .crud_user_relationship import user_relationship # For block/mute list
from app.schemas.enums import RelationshipTypeEnum # For block/mute list


class CRUDComment(CRUDBase[Comment, CommentCreate, CommentUpdate]):
    def create_with_author_and_post(
        self, db: Session, *, obj_in: CommentCreate, author_id: uuid.UUID, post_id: uuid.UUID
    ) -> Comment:
        """
        Create a new comment associated with an author and a post.
        """
        db_obj = Comment(
            content=obj_in.content,
            author_id=author_id,
            post_id=post_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: uuid.UUID) -> Optional[Comment]:
        """
        Get a single comment by its anonymous_comment_id.
        """
        return db.execute(
            select(self.model)
            .options(joinedload(self.model.author)) # Eager load author for CommentRead
            .filter(self.model.anonymous_comment_id == id)
        ).scalar_one_or_none()

    def get_multi_by_post(
        self,
        db: Session,
        *,
        post_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        current_user_anonymous_id: Optional[uuid.UUID] = None
    ) -> List[Comment]:
        """
        Get multiple comments for a specific post, ordered by creation date (newest first).
        Optionally filters out comments from users muted/blocked by current_user.
        """
        query = db.query(self.model).filter(Comment.post_id == post_id)

        if current_user_anonymous_id:
            excluded_author_ids = user_relationship.get_target_ids_by_actor_and_type(
                db,
                actor_anonymous_id=current_user_anonymous_id,
                relationship_types=[RelationshipTypeEnum.MUTE, RelationshipTypeEnum.BLOCK]
            )
            if excluded_author_ids:
                query = query.filter(Comment.author_id.notin_(excluded_author_ids))

        return query.options(joinedload(self.model.author)) \
                    .order_by(desc(Comment.created_at)) \
                    .offset(skip) \
                    .limit(limit) \
                    .all()
    def get_multi_by_author_anonymous_id(
        self, db: Session, *, author_anonymous_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[Comment]:
        """
        Get multiple comments by a specific author, ordered by creation date (newest first).
        Eager loads author and post relationships for CommentRead schema.
        """
        return (
            db.query(self.model)
            .filter(Comment.author_id == author_anonymous_id)
            .options(joinedload(self.model.author), joinedload(self.model.post)) # Eager load author and post
            .order_by(desc(Comment.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(
        self, db: Session, *, db_obj: Comment, obj_in: Union[CommentUpdate, Dict[str, Any]]
    ) -> Comment:
        """
        Update a comment.
        Note: Authorization (e.g., ensuring only the author can update)
        should be handled at the API endpoint level.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def remove(self, db: Session, *, id: uuid.UUID) -> Optional[Comment]:
        """
        Remove a comment by its anonymous_comment_id.
        Note: Authorization (e.g., ensuring only the author or admin can delete)
        should be handled at the API endpoint level.
        """
        # .get() works on the primary key, which is 'id' (Integer) for Comment model.
        # We need to fetch by anonymous_comment_id for consistency with how 'id' is used in API.
        obj = db.query(self.model).filter(self.model.anonymous_comment_id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def process_comment_vote(
        self,
        db: Session,
        *,
        comment_anonymous_id: uuid.UUID,
        user_anonymous_id: uuid.UUID,
        requested_vote_type: VoteTypeEnum
    ) -> Optional[Comment]:
        """
        Process a vote (upvote or downvote) on a comment.
        If the user votes the same way again, the vote is removed (unvote).
        If the user changes their vote, the existing vote is updated.
        """
        comment = self.get(db, id=comment_anonymous_id) # Use existing get method

        if not comment:
            return None # Comment not found

        existing_vote_log = db.execute(
            select(CommentVoteLog).where(
                CommentVoteLog.user_anonymous_id == user_anonymous_id,
                CommentVoteLog.comment_anonymous_id == comment.anonymous_comment_id
            )
        ).scalar_one_or_none()

        if existing_vote_log:
            # User has voted on this comment before
            if existing_vote_log.vote_type == requested_vote_type:
                # User is clicking the same vote type again - effectively "unvoting"
                db.delete(existing_vote_log)
                if requested_vote_type == VoteTypeEnum.UPVOTE:
                    comment.upvotes = max(0, comment.upvotes - 1)
                else:  # DOWNVOTE
                    comment.downvotes = max(0, comment.downvotes - 1)
            else:
                # User is changing their vote (e.g., from upvote to downvote)
                existing_vote_log.vote_type = requested_vote_type
                if requested_vote_type == VoteTypeEnum.UPVOTE: # Was downvote, now upvote
                    comment.downvotes = max(0, comment.downvotes - 1)
                    comment.upvotes += 1
                else:  # Was upvote, now downvote
                    comment.upvotes = max(0, comment.upvotes - 1)
                    comment.downvotes += 1
                db.add(existing_vote_log)
        else:
            # New vote for this user on this comment
            new_vote_log = CommentVoteLog(
                user_anonymous_id=user_anonymous_id,
                comment_anonymous_id=comment.anonymous_comment_id,
                vote_type=requested_vote_type
            )
            db.add(new_vote_log)
            if requested_vote_type == VoteTypeEnum.UPVOTE:
                comment.upvotes += 1
            else:  # DOWNVOTE
                comment.downvotes += 1

        db.add(comment) # Add to session to save changes to upvotes/downvotes
        db.commit()
        db.refresh(comment) # Refresh to get any DB-side updates and ensure relationships are current
        return comment

    def delete_all_comments_by_author(self, db: Session, author_anonymous_id: uuid.UUID) -> int:
        """Deletes all comments by a given author and returns the count of deleted comments."""
        comments_to_delete = db.query(self.model).filter(self.model.author_id == author_anonymous_id).all()
        count = len(comments_to_delete)
        if count > 0:
            for comment_obj in comments_to_delete:
                db.delete(comment_obj)
            db.commit()
        return count

comment = CRUDComment(Comment)