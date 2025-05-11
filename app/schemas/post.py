from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing import Optional
from datetime import datetime
import uuid
from app.db.models.post_vote_log import VoteTypeEnum

# Define a simple schema for author details to be embedded in PostRead
class AuthorRead(BaseModel):
    id: uuid.UUID = Field(validation_alias='anonymous_id') # This will be the user's anonymous_id
    username: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Shared properties
class PostBase(BaseModel):
    title: Optional[str] = None
    content: str

# Properties to receive on post creation
class PostCreate(PostBase):
    # user_id will be set based on the authenticated user in the endpoint
    pass

# Properties to receive on post update
class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    # is_active could be updated by admins/moderators or specific user actions
    is_active: Optional[bool] = None

class PostVoteCreate(BaseModel):
    vote_type: VoteTypeEnum

# Properties to return to client
class PostRead(PostBase):
    # Use a computed field to expose anonymous_post_id as 'id'
    orm_anonymous_post_id: uuid.UUID = Field(validation_alias='anonymous_post_id', exclude=True)

    @computed_field # type: ignore[misc]
    @property
    def id(self) -> uuid.UUID:
        return self.orm_anonymous_post_id

    # We'll need to fetch author details separately or join them
    # For now, let's include the author's anonymous_id
    # In a more advanced setup, we might embed a UserRead schema here.
    author: AuthorRead # Embed author details

    is_active: bool
    is_edited: bool
    upvotes: int
    downvotes: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)