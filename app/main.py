from fastapi import FastAPI
import uvicorn
# from app.db.session import create_db_and_tables
from app.db.models import user
from app.api.v1.api import api_router as api_v1_router
from app.core.config import settings
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send # Add these imports


class RawRequestLoggerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            print(f"--- MIDDLEWARE LOG ---")
            print(f"Scope Type: {scope['type']}")
            print(f"Path: {scope.get('path')}")
            print(f"Headers: {scope.get('headers')}") # This will show the initial HTTP headers
            print(f"----------------------")
        await self.app(scope, receive, send)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Anonymous Hub, a platform for anonymous connection and support.",
    version="0.1.0",
)

# Add the RawRequestLoggerMiddleware as the VERY FIRST middleware
app.add_middleware(RawRequestLoggerMiddleware)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

# Mount static files directory
# This will serve files from a directory named "static" at the project root
# If avatars are now served from GCS and this was their only purpose,
# this line can be removed. Ensure the 'static' directory is also removed if no longer needed.
# app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def on_startup():
    print("Creating database and tables...")
    #create_db_and_tables()


@app.get("/")
async def read_root():
    return {"message": "Welcome to Anonymous Hub API"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__== "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", reload=True)