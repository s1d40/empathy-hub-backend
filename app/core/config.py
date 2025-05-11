import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Empathy Hub API"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/db")

    class Config:
        case_sensitive = True


settings = Settings()

# For debugging purposes:
print(f"DEBUG: Loaded DATABASE_URL: '{settings.DATABASE_URL}'")
print(f"DEBUG: Type of DATABASE_URL: {type(settings.DATABASE_URL)}")