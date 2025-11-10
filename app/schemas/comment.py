import uuid
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from .user import AuthorRead
from .enums import VoteTypeEnum

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=1000)

class CommentVoteCreate(BaseModel):
    vote_type: VoteTypeEnum

class CommentRead(CommentBase):
    anonymous_comment_id: uuid.UUID
    author: AuthorRead
    created_at: datetime
    updated_at: Optional[datetime] = None
    upvotes: int
    downvotes: int
    post_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
