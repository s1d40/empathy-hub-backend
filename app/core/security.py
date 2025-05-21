from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import ValidationError
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# For password hashing (not directly used for anonymous users' primary auth, but good to have)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# We might add a function here later to decode tokens for the dependency
def decode_access_token(token_data: str) -> Optional[dict]: # Or Optional[TokenPayload] if you parse into Pydantic model
    """
    Decodes the JWT access token.
    Returns the payload dictionary if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token_data, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # You might want to validate the payload structure here, e.g., using TokenPayload schema
        # For example:
        # token_payload = TokenPayload(**payload)
        # return token_payload # if you want to return the Pydantic model
        return payload # if you just want the raw dictionary
    except JWTError: # Catches expired signature, invalid signature, etc.
        return None
    except ValidationError: # If you use Pydantic model validation for payload
        return None