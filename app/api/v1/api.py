from fastapi import APIRouter

from app.api.v1.endpoints import users, user_actions, reports # Add reports
from app.api.v1.endpoints import posts, auth, chat, avatars, comments # Added chat import


api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts-and-comments"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(chat.router, prefix="/chats", tags=["chat"]) # Added chat router
api_router.include_router(comments.router, prefix="/posts", tags=["comments"]) # Or prefix="/comments" if you prefer
api_router.include_router(avatars.router, prefix="/avatars", tags=["avatars"]) # Added avatars router
api_router.include_router(user_actions.router, prefix="/users", tags=["user-actions"]) 
api_router.include_router(reports.router, prefix="/reports", tags=["reports"]) # Add reports router
# Add other endpoint routers here