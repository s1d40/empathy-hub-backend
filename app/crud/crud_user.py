from sqlalchemy.orm import Session
from app.db.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional, List
import uuid
import random # Import the random module
from app.schemas.enums import ChatAvailabilityEnum
from app.core.config import settings # Import settings



def get_user(db: Session, user_id: int) -> Optional[User]: # type: ignore
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_anonymous_id(db: Session, anonymous_id: uuid.UUID) -> Optional[User]: # Changed type hint to uuid.UUID
    # Compare directly with the UUID object since User.anonymous_id is PG_UUID(as_uuid=True)
    return db.query(User).filter(User.anonymous_id == anonymous_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user_in: UserCreate) -> User: # Changed parameter name for consistency
    generated_anonymous_id = str(uuid.uuid4()) # This is for the user's main anonymous_id
    final_username = user_in.username

    if not final_username:
        # Generate an "Anonymous" username if none provided
        # We'll try a few times with different parts of the UUID if there's a collision
        temp_uuid_for_username = uuid.uuid4()
        for i in range(4): # Try up to 4 different segments or new UUIDs
            # Take different 4-char segments or generate new UUIDs
            # For simplicity, let's try different segments of the same UUID first, then a new one.
            # A more robust way might be to generate a new UUID each time.
            # For this example, we'll just use the first 4 chars and regenerate UUID if needed.
            segment = str(temp_uuid_for_username).replace("-", "")[i*4 : (i*4)+4].upper()
            candidate_username = f"Anonymous{segment}"
            if not get_user_by_username(db, username=candidate_username):
                final_username = candidate_username
                break
            if i == 3: # If all segments from one UUID failed, try a new UUID once more
                temp_uuid_for_username = uuid.uuid4() 
        else: # If loop completes without break (all attempts failed)
            # Extremely unlikely, but as a fallback, append more of the UUID
            final_username = f"Anonymous{str(uuid.uuid4())[:8].upper()}" 
            # At this point, if it still collides, the DB unique constraint will catch it.
    elif get_user_by_username(db, username=final_username):
        # This case should ideally be handled by the API endpoint raising an HTTPException
        # before calling create_user, but as a safeguard:
        raise ValueError(f"Username '{final_username}' already exists.")

    # Assign random avatar if not provided by the client
    avatar = user_in.avatar_url
    if not avatar:
        if settings.DEFAULT_AVATAR_FILENAMES:
            # Select a random avatar filename from the list
            selected_avatar_filename = random.choice(settings.DEFAULT_AVATAR_FILENAMES)
            avatar = f"http://192.168.1.120:8000{settings.AVATAR_BASE_URL}{selected_avatar_filename}"
        else:
            # This case handles if settings.DEFAULT_AVATAR_FILENAMES is empty or not configured.
            # random.choice would raise an IndexError if the list is empty,
            # so this 'else' branch (or an explicit check before random.choice) is important.
            print("Warning: settings.DEFAULT_AVATAR_FILENAMES is not configured or is empty. Using fallback avatar.")
            avatar = f"{settings.AVATAR_BASE_URL}default.jpg" # Ensure 'default.jpg' exists
    
    # Prepare user data for model creation
    user_data = {
        "anonymous_id": generated_anonymous_id,
        "username": final_username,
        "bio": user_in.bio,
        "pronouns": user_in.pronouns,
        "avatar_url": avatar,
    }
    # If chat_availability is provided in the input, use it. Otherwise, DB default applies.
    if user_in.chat_availability is not None:
        user_data["chat_availability"] = user_in.chat_availability

    db_user = User(
        **user_data
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user_by_anonymous_id(db: Session, anonymous_id: uuid.UUID) -> Optional[User]:
    """
    Delete a user by their anonymous ID.
    Returns the deleted user object or None if not found.
    """
    # Fetch the user using the anonymous_id
    db_user = db.query(User).filter(User.anonymous_id == anonymous_id).first()
    if db_user:
        # Store a representation before deleting if needed for response,
        # but typically delete endpoints return 204 No Content or the ID.
        # For simplicity, we'll just return the object before deletion.
        deleted_user_obj = db_user # Keep a reference before deleting
        db.delete(db_user)
        db.commit()
        return deleted_user_obj # Return the object that was deleted
    return None # User not found