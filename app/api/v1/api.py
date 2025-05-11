from fastapi import APIRouter

from app.api.v1.endpoints import users
from app.api.v1.endpoints import posts


api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
# Add other endpoint routers here