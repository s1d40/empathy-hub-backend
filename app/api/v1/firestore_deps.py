from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import settings
from app.services.firestore_services import user_service
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token", auto_error=False)

def get_current_user_firestore(token: str = Depends(oauth2_scheme)) -> Optional[dict]:
    """
    Decodes the JWT token and retrieves the user from Firestore.
    If the token is invalid or not provided, returns None.
    """
    if token is None:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        anonymous_id: str = payload.get("anonymous_id")
        if anonymous_id is None:
            return None
    except JWTError:
        return None

    user = user_service.get_user_by_anonymous_id(anonymous_id=anonymous_id)
    if user is None:
        return None
    return user

def get_current_active_user_firestore(current_user: dict = Depends(get_current_user_firestore)) -> dict:
    """
    Checks if the current user is active.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.get("is_active"):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_optional_current_user_firestore(current_user: dict = Depends(get_current_user_firestore)) -> Optional[dict]:
    """
    Returns the current user if they are authenticated, otherwise returns None.
    """
    return current_user
