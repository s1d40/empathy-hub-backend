from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from datetime import timedelta
import uuid # Import the uuid module

from app import crud, schemas
from app.api.v1 import deps
from app.core.security import create_access_token
from app.core.config import settings

router = APIRouter()

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    db: Session = Depends(deps.get_db),
    # The form field is named "username" due to OAuth2 password flow conventions,
    # but we will treat its value as an anonymous_id for lookup.
    identifier: str = Form(..., alias="username")
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Expects an existing anonymous_id to be provided in the 'username' form field.
    """
    cleaned_identifier = identifier.strip() # Strip whitespace
    try:
        anonymous_uuid = uuid.UUID(cleaned_identifier) # Convert to UUID object
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Anonymous ID format. Please provide a valid UUID.",
        )

    user = crud.crud_user.get_user_by_anonymous_id(db, anonymous_id=anonymous_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with the provided identifier (anonymous_id). Please ensure the user exists.",
        )
    #At this point, user exists (either pre-existing or just crated)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token  = create_access_token(
        data={"sub": user.username, "anonymous_id": str(user.anonymous_id)}, # Keep str() here for JWT payload
         expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "anonymous_id": user.anonymous_id # Pass the UUID object directly

    }
    

        
        