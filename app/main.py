import os
import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials as firebase_credentials
from google.auth import credentials as google_credentials
from contextlib import asynccontextmanager # Import asynccontextmanager

from app.core.config import settings
from app.api.v1.endpoints import (
    auth as auth_router,
    users as users_router,
    posts as posts_router,
    comments as comments_router,
    user_actions as user_actions_router,
    reports as reports_router,
    chat as chat_router,
    avatars as avatars_router,
    notifications as notifications_router, # Import the new notifications router
)
from app.core.chat_manager import manager # Import manager

# --- Firebase Initialization ---
print("Initializing Firebase Admin SDK...")
print(f"DEBUG (main.py): GCP_PROJECT_ID from settings: {settings.GCP_PROJECT_ID}")
print(f"DEBUG (main.py): FIRESTORE_EMULATOR_HOST from settings: {settings.FIRESTORE_EMULATOR_HOST}")
if not firebase_admin._apps:
    try:
        # Initialize Firebase Admin SDK.
        # It will automatically use FIRESTORE_EMULATOR_HOST if set in environment.
        # For production, it will use Application Default Credentials.
        firebase_admin.initialize_app(options={'projectId': settings.GCP_PROJECT_ID})
        print("Firebase Admin SDK initialized.")
    except Exception as e:
        print(f"Firebase initialization failed: {e}")
else:
    print("Firebase app already initialized.")

@asynccontextmanager
async def lifespan_context_manager(app: FastAPI):
    # Startup
    print("Main app lifespan startup: Starting Pub/Sub subscriber...")
    manager.start_pubsub_subscriber()
    yield
    # Shutdown
    print("Main app lifespan shutdown: Stopping Pub/Sub subscriber...")
    manager.stop_pubsub_subscriber()

# This comment is added to trigger a new Cloud Run deployment after IAM changes.


app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Firestore Backend",
    description="API for Empathy Hub, running on a serverless Firestore backend.",
    version="0.2.0",
    lifespan=lifespan_context_manager # Register the lifespan context manager
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Use the list from settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Firestore Backend API Router ---
api_router_firestore = APIRouter()
api_router_firestore.include_router(auth_router.router, prefix="/auth", tags=["auth"])
api_router_firestore.include_router(users_router.router, prefix="/users", tags=["users"])
api_router_firestore.include_router(posts_router.router, prefix="/posts", tags=["posts"])
# Note: The path for comments is now more RESTful, directly under the posts resource
api_router_firestore.include_router(comments_router.router, prefix="/posts", tags=["comments"])
api_router_firestore.include_router(user_actions_router.router, prefix="/user-actions", tags=["user-actions"])
api_router_firestore.include_router(reports_router.router, prefix="/reports", tags=["reports"])
api_router_firestore.include_router(chat_router.router, prefix="/chat", tags=["chat"])
api_router_firestore.include_router(avatars_router.router, prefix="/avatars", tags=["avatars"])
api_router_firestore.include_router(notifications_router.router, prefix="/notifications", tags=["notifications"]) # Include the new notifications router

app.include_router(api_router_firestore, prefix=settings.API_V1_STR)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return {"message": "Welcome to Empathy Hub API (Firestore Backend)"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__== "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", reload=True)
