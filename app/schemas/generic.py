from pydantic import BaseModel
from typing import Optional

class DeletionSummary(BaseModel):
    message: str
    deleted_count: int

class AllContentDeletionSummary(BaseModel):
    posts_deleted: int
    comments_deleted: int
    chat_messages_deleted: int
    message: str