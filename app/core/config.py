import os
from dotenv import load_dotenv
from datetime import timedelta
from pydantic_settings import BaseSettings
from app.scripts.generate_avatar_filenames import avatar_filenames
from typing import Optional

# This import is where the traceback indicates the ImportError occurs.
# Fixing the Settings class structure below is the first step.

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Anonymous Hub API"
    API_V1_STR: str = "/api/v1"
    DEFAULT_AVATAR_FILENAMES: list[str] = avatar_filenames # Use the imported list
    # AVATAR_BASE_URL should now be the full public URL to your GCS bucket's avatar folder
    # Example: "https://storage.googleapis.com/your-bucket-name/static/avatars/"
    # Ensure it ends with a trailing slash.
    AVATAR_BASE_URL: str = os.getenv("AVATAR_BASE_URL", "https://storage.googleapis.com/empathy-hub-avatars-anonymous-hubs-477707/static/avatars/")
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:43391",      # Previous frontend origin
        "http://127.0.0.1:44093",
        "http://localhost:36159",      # Your current frontend origin
        'http://192.168.1.120:8000',
        'http://0.0.0.0:8000',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        "https://sfaisolutions.com", # Deployed frontend origin
    ]
    # GCP and Firebase Settings
    GCP_PROJECT_ID: str
    # For live deployment, ensure FIRESTORE_EMULATOR_HOST environment variable is NOT set.
    FIRESTORE_EMULATOR_HOST: Optional[str] = os.getenv("FIRESTORE_EMULATOR_HOST") # e.g., "localhost:8080"
    # For live deployment, ensure PUBSUB_EMULATOR_HOST environment variable is NOT set.
    PUBSUB_EMULATOR_HOST: Optional[str] = os.getenv("PUBSUB_EMULATOR_HOST") # e.g., "localhost:8085"

    #JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "secret_key")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 *24 * 7 # 7 days
    INSTANCE_ID: str = os.getenv("K_REVISION", "local") # Unique identifier for each Cloud Run instance

    class Config:
        case_sensitive = True


settings = Settings()

# For debugging purposes:
print(f"DEBUG: Loaded DEFAULT_AVATAR_FILENAMES count: {len(settings.DEFAULT_AVATAR_FILENAMES) if settings.DEFAULT_AVATAR_FILENAMES else 'Not loaded or empty'}")
print(f"DEBUG: GCP_PROJECT_ID from settings: {settings.GCP_PROJECT_ID}")
print(f"DEBUG: FIRESTORE_EMULATOR_HOST from settings: {settings.FIRESTORE_EMULATOR_HOST}")
print(f"DEBUG: INSTANCE_ID from settings: {settings.INSTANCE_ID}")
