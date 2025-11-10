from fastapi import APIRouter, Depends, HTTPException, status, Form
from datetime import timedelta
import uuid
from app import schemas
from app.services.firestore_services import user_service
from app.core.security import create_access_token
from app.core.config import settings

router = APIRouter()

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(identifier: str = Form(..., alias="username")):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Expects an existing anonymous_id to be provided in the 'username' form field.
    """
    cleaned_identifier = identifier.strip()
    try:
        # The service expects a string, so we don't need to convert to UUID object here
        uuid.UUID(cleaned_identifier) # Still validate the format
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Anonymous ID format. Please provide a valid UUID.",
        )

    user = user_service.get_user_by_anonymous_id(anonymous_id=cleaned_identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with the provided identifier (anonymous_id).",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['username'], "anonymous_id": user['anonymous_id']},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user['username'],
        "anonymous_id": user['anonymous_id']
    }

    

        
        