from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing import Optional
from datetime import datetime
from .enums import ChatAvailabilityEnum
import uuid

# Properties common to user creation and potentially updates
class UserBase(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    chat_availability: Optional[ChatAvailabilityEnum] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = True

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
    # It's prefixed with 'orm_' to indicate its origin and excluded from the final JSON output.
    orm_anonymous_id: uuid.UUID = Field(validation_alias='anonymous_id', exclude=True)

    @computed_field # type: ignore[misc] # Suppress Pylance warning if any
    @property
    def id(self) -> str:
        return str(self.orm_anonymous_id)

    model_config = ConfigDict(from_attributes=True)


class AuthorRead(BaseModel):
    id: uuid.UUID = Field(validation_alias='anonymous_id') # This will be the user's anonymous_id, Pydantic handles UUID -> str serialization
    username: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserInDB(UserBase):
    anonymous_id: str
    created_at: datetime
    updated_at: datetime