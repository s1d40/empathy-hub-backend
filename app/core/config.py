import os
from dotenv import load_dotenv
from datetime import timedelta
from pydantic_settings import BaseSettings
from app.scripts.generate_avatar_filenames import avatar_filenames
# This import is where the traceback indicates the ImportError occurs.
# Fixing the Settings class structure below is the first step.

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Empathy Hub API"
    API_V1_STR: str = "/api/v1"
    DEFAULT_AVATAR_FILENAMES: list[str] = avatar_filenames # Use the imported list
    AVATAR_BASE_URL: str = "/static/avatars/"
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:43391",      # Previous frontend origin
        "http://127.0.0.1:44093",
        "http://localhost:36159",      # Your current frontend origin
        'http://192.168.1.120:8000',
        'http://0.0.0.0:8000',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        # Add any other origins if needed, e.g., your deployed frontend URL
    ]

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/db")
    #JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "secret_key")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 *24 * 7 # 7 days

    class Config:
        case_sensitive = True


settings = Settings()

# For debugging purposes:
print(f"DEBUG: Loaded DATABASE_URL: '{settings.DATABASE_URL}'")
print(f"DEBUG: Type of DATABASE_URL: {type(settings.DATABASE_URL)}")
print(f"DEBUG: Loaded DEFAULT_AVATAR_FILENAMES count: {len(settings.DEFAULT_AVATAR_FILENAMES) if settings.DEFAULT_AVATAR_FILENAMES else 'Not loaded or empty'}")
