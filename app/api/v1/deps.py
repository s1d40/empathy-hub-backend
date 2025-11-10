from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import uuid
from typing import Optional

from app.core.config import settings
from app.schemas.user import UserInDB
from app.services.firestore_services import user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    base_credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        anonymous_id_str: str = payload.get("anonymous_id")
        if anonymous_id_str is None:
            base_credentials_exception.detail = "Anonymous ID not found in token payload"
            raise base_credentials_exception
        
        try:
            uuid.UUID(anonymous_id_str)
        except ValueError as e:
            base_credentials_exception.detail = f"Invalid Anonymous ID format in token: {e}"
            raise base_credentials_exception

    except JWTError as e:
        base_credentials_exception.detail = f"Invalid token: {e}"
        raise base_credentials_exception
    
    user_dict = user_service.get_user_by_anonymous_id(anonymous_id_str)
    if user_dict is None:
        base_credentials_exception.detail = "User not found"
        raise base_credentials_exception
    
    return UserInDB(**user_dict)

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

async def get_optional_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[UserInDB]:
    if not token:
        return None
    try:
        return await get_current_user(token)
    except HTTPException:
        return None