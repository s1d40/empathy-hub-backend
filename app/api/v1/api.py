from fastapi import APIRouter

from app.api.v1.endpoints import users
from app.api.v1.endpoints import posts, auth


api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts-and-comments"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
# Add other endpoint routers here