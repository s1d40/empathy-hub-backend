from pydantic import BaseModel
from typing import Optional
import uuid # Import the uuid module

class Token(BaseModel):
    access_token: str
    token_type: str
    username: Optional[str] = None
    anonymous_id: Optional[uuid.UUID] = None # Changed from str to uuid.UUID