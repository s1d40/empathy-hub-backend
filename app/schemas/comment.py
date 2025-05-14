import uuid
from typing import Optional
from pydantic import BaseModel, Field, computed_field, ConfigDict # Added ConfigDict
from datetime import datetime
from .user import AuthorRead # Assuming AuthorRead is defined in schemas.user
from app.db.models.post_vote_log import VoteTypeEnum # Reusing VoteTypeEnum

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=1000)

class CommentVoteCreate(BaseModel):
    vote_type: VoteTypeEnum

class CommentRead(CommentBase):
    orm_anonymous_comment_id: uuid.UUID = Field(validation_alias='anonymous_comment_id', exclude=True)

    @computed_field # type: ignore[misc]
    @property
    def id(self) -> uuid.UUID: # Expose anonymous_comment_id as 'id'
        return self.orm_anonymous_comment_id

    author: AuthorRead # Embed author details
    created_at: datetime
    updated_at: Optional[datetime] = None
    upvotes: int
    downvotes: int
    post_id: uuid.UUID # You might want to include the parent post's anonymous_id too

    model_config = ConfigDict(from_attributes=True)
