from fastapi import APIRouter
from typing import List
from app.core.config import settings


# Import the constants from crud_user.py
# We might want to move these to a central config later, but for now, this is fine.




router = APIRouter()


@router.get("/defaults", response_model=List[str])
def get_default_avatars():
    """
    Retrieve a list of full URLs for the default user avatars.
    """
    if not settings.DEFAULT_AVATAR_FILENAMES:
        return []

    full_avatar_urls = [f"{settings.AVATAR_BASE_URL}{filename}" for filename in settings.DEFAULT_AVATAR_FILENAMES]
    return full_avatar_urls


