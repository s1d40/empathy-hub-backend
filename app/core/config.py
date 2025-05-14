import os
from dotenv import load_dotenv
from datetime import timedelta
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Empathy Hub API"
    API_V1_STR: str = "/api/v1"

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