from fastapi import FastAPI
# from app.db.session import create_db_and_tables
from app.db.models import user
from app.api.v1.api import api_router as api_v1_router
from app.core.config import settings


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Empathy Hub, a platform for empathic connection and support.",
    version="0.1.0",
)
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def on_startup():
    print("Creating database and tables...")
    #create_db_and_tables()


@app.get("/")
async def read_root():
    return {"message": "Welcome to Empathy Hub API"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}