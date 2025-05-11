from sqlalchemy.orm import Session
from app.db.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional, List
import uuid
from app.schemas.enums import ChatAvailabilityEnum # Import if needed for explicit setting

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_anonymous_id(db: Session, anonymous_id: str) -> Optional[User]:
    return db.query(User).filter(User.anonymous_id == anonymous_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user: UserCreate) -> User:
    generated_anonymous_id = str(uuid.uuid4()) # This is for the user's main anonymous_id
    final_username = user.username

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

    # Assign default avatar if not provided by the client
    avatar = user.avatar_url
    if not avatar:
        # Use the generated_anonymous_id to make the default avatar unique per user
        avatar = f"https://i.pravatar.cc/150?u={generated_anonymous_id}"
    
    # Prepare user data for model creation
    user_data = {
        "anonymous_id": generated_anonymous_id,
        "username": final_username,
        "bio": user.bio,
        "pronouns": user.pronouns,
        "avatar_url": avatar,
    }
    # If chat_availability is provided in the input, use it. Otherwise, DB default applies.
    if user.chat_availability is not None:
        user_data["chat_availability"] = user.chat_availability

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

def delete_user(db: Session, user_id: int) -> Optional[User]:
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user