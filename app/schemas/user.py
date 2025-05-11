from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing import Optional
from datetime import datetime
from .enums import ChatAvailabilityEnum

# Properties common to user creation and potentially updates
class UserBase(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    chat_availability: Optional[ChatAvailabilityEnum] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None

# Properties to receive on user creation
class UserCreate(UserBase):
    # anonymous_id: str # This is the public-facing ID the client will send
    pass
# Properties to receive on user update
class UserUpdate(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    chat_availability: Optional[ChatAvailabilityEnum] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None

# Properties to return to client
class UserRead(UserBase): # Inherits username and avatar_url from UserBase
    # Timestamps are directly from the model
    chat_availability: ChatAvailabilityEnum
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    # This field captures the 'anonymous_id' from the ORM model.
    # It's prefixed with an underscore to indicate it's for internal schema use
    # and excluded from the final JSON output.
    # `validation_alias` ensures it's populated from `model.anonymous_id` when `from_attributes=True`.
    orm_anonymous_id: str = Field(validation_alias='anonymous_id', exclude=True)

    # This computed field will be the public 'id' in the JSON response.
    # It uses the value captured by _orm_anonymous_id.
    @computed_field # type: ignore[misc] # Suppress Pylance warning if any
    @property
    def id(self) -> str:
        return self.orm_anonymous_id

    model_config = ConfigDict(from_attributes=True)