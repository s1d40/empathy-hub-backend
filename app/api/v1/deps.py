from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app.db.session import get_db
from app.db.models.user import User
from app.crud import crud_user

# This scheme will look for a token in the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token") # tokenUrl is a dummy here, as we don't have a traditional login form

async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    # Define a base exception, we'll update its detail based on the specific error
    base_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    # print(f"get_current_user: Received token: {token[:20]}...") # Log received token (truncated)
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # print(f"get_current_user: Token decoded. Payload: {payload}") # Log decoded payload

        # The token payload should contain 'anonymous_id' directly, not 'sub' for anonymous_id
        # Based on previous discussions, 'anonymous_id' is the key.
        anonymous_id_str: str = payload.get("anonymous_id") # Changed from "sub" to "anonymous_id"
        if anonymous_id_str is None:
            # print("get_current_user: 'anonymous_id' not found in token payload.")
            # Update detail for missing anonymous_id
            base_credentials_exception.detail = "Anonymous ID not found in token payload"
            raise base_credentials_exception
        # print(f"get_current_user: Extracted anonymous_id_str from payload: {anonymous_id_str}")

        # Attempt to parse the string as a UUID
        try:
            anonymous_id = uuid.UUID(anonymous_id_str)
            # print(f"get_current_user: Parsed anonymous_id_str to UUID: {anonymous_id}")
        except ValueError as e:
            # print(f"get_current_user: Failed to parse anonymous_id_str '{anonymous_id_str}' as UUID.")
            # Update detail for invalid UUID format
            base_credentials_exception.detail = f"Invalid Anonymous ID format in token: {e}"
            raise base_credentials_exception

    except JWTError as e:
        # print(f"get_current_user: JWTError during token processing: {e}")
        # Update detail for JWT errors (e.g., invalid signature, expired)
        base_credentials_exception.detail = f"Invalid token: {e}"
        raise base_credentials_exception
    except ValidationError as e: # Catch Pydantic validation errors if payload was validated against a model
        # print(f"get_current_user: ValidationError during token processing: {e}")
        # Update detail for validation errors
        base_credentials_exception.detail = f"Token payload validation failed: {e}"
        raise base_credentials_exception
    
    user = crud_user.get_user_by_anonymous_id(db, anonymous_id=anonymous_id)
    if user is None:
        # print(f"get_current_user: User not found in DB for anonymous_id: {anonymous_id}") # Already logged
        # Update detail for user not found
        base_credentials_exception.detail = "User not found"
        raise base_credentials_exception
    # print(f"get_current_user: User found in DB: User ID {user.id}, Anonymous ID {user.anonymous_id}, Username {user.username}")
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    # print(f"Inside get_current_active_user. Received user: {current_user}") # Log the user object
    if not current_user.is_active:
        # print("User is NOT active. Raising HTTPException.") # Log if inactive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    # print("User is active. Returning user.") # Log if active
    return current_user