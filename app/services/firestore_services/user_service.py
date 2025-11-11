import uuid
import random
from firebase_admin import firestore
from app.schemas.user import UserCreate, UserUpdate
from app.core.config import settings
from typing import List, Optional
from app.services.firestore_services import post_service, comment_service

# This service replaces the functionality of crud/crud_user.py for a Firestore database.

def get_users_collection():
    """Returns the 'users' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('users')

# --- Service Functions ---

def get_user_by_anonymous_id(anonymous_id: str) -> Optional[dict]:
    """
    Retrieves a user document by its anonymous_id (which is the document ID).
    """
    users_collection = get_users_collection()
    doc_ref = users_collection.document(anonymous_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_users_by_anonymous_ids(anonymous_ids: List[str]) -> List[dict]:
    """
    Retrieves multiple user documents by their anonymous_ids in a single batch.
    """
    db = firestore.client()
    refs = [get_users_collection().document(user_id) for user_id in anonymous_ids]
    docs = db.get_all(refs)
    return [doc.to_dict() for doc in docs if doc.exists]

def get_user_by_username(username: str) -> Optional[dict]:
    """
    Retrieves a user by their username.
    """
    users_collection = get_users_collection()
    docs = users_collection.where('username', '==', username).limit(1).stream()
    for doc in docs:
        return doc.to_dict()
    return None

def get_users(skip: int = 0, limit: int = 100) -> List[dict]:
    """
    Retrieves a list of users with pagination.
    """
    users_collection = get_users_collection()
    docs = users_collection.limit(limit).offset(skip).stream()
    return [doc.to_dict() for doc in docs]

def create_user(user_in: UserCreate) -> dict:
    """
    Creates a new user document in Firestore, ensuring username uniqueness within a transaction.
    """
    db = firestore.client()
    users_collection = get_users_collection()
    generated_anonymous_id = str(uuid.uuid4())

    @firestore.transactional
    def create_user_in_transaction(transaction):
        final_username = user_in.username
        if not final_username:
            while True:
                segment = str(uuid.uuid4()).replace("-", "")[:4].upper()
                candidate_username = f"Anonymous{segment}"
                # Check for username existence within the transaction
                query = users_collection.where('username', '==', candidate_username).limit(1)
                docs = query.stream(transaction=transaction)
                if not any(docs):
                    final_username = candidate_username
                    break
        else:
            # Check for username existence within the transaction
            query = users_collection.where('username', '==', final_username).limit(1)
            docs = query.stream(transaction=transaction)
            if any(docs):
                raise ValueError(f"Username '{final_username}' already exists.")

        avatar = user_in.avatar_url
        if not avatar and settings.DEFAULT_AVATAR_FILENAMES:
            selected_avatar_filename = random.choice(settings.DEFAULT_AVATAR_FILENAMES)
            avatar = f"{settings.AVATAR_BASE_URL}{selected_avatar_filename}"

        user_data = {
            "anonymous_id": generated_anonymous_id,
            "username": final_username,
            "bio": user_in.bio,
            "pronouns": user_in.pronouns,
            "avatar_url": avatar,
            "chat_availability": user_in.chat_availability.value if user_in.chat_availability else 'open_to_chat',
            "is_active": True,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        user_ref = users_collection.document(generated_anonymous_id)
        transaction.set(user_ref, user_data)
        return user_ref

    try:
        transaction = db.transaction()
        user_ref = create_user_in_transaction(transaction)
        # Re-fetch the document to get server-resolved timestamps
        created_doc = user_ref.get()
        if created_doc.exists:
            return created_doc.to_dict()
        else:
            raise ValueError("User creation failed unexpectedly after transaction.")
    except Exception as e:
        # Log the exception e
        raise e

def update_user(anonymous_id: str, user_in: UserUpdate) -> Optional[dict]:
    """
    Updates a user document in Firestore, ensuring username uniqueness within a transaction.
    """
    db = firestore.client()
    users_collection = get_users_collection()
    user_ref = users_collection.document(anonymous_id)

    @firestore.transactional
    def update_user_in_transaction(transaction):
        doc = user_ref.get(transaction=transaction)
        if not doc.exists:
            return None

        update_data = user_in.model_dump(exclude_unset=True)
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP

        if 'username' in update_data and update_data['username'] != doc.to_dict().get('username'):
            # Check for username existence within the transaction
            query = users_collection.where('username', '==', update_data['username']).limit(1)
            docs = query.stream(transaction=transaction)
            for existing_user_doc in docs:
                if existing_user_doc.id != anonymous_id:
                    raise ValueError(f"Username '{update_data['username']}' already exists.")
        
        transaction.update(user_ref, update_data)
        return True

    try:
        transaction = db.transaction()
        result = update_user_in_transaction(transaction)
        if result:
            # Re-fetch the document to get server-resolved timestamps
            updated_doc = user_ref.get()
            return updated_doc.to_dict()
        return None
    except Exception as e:
        # Log the exception e
        raise e

def delete_user(anonymous_id: str) -> bool:
    """
    Deletes a user and all of their content (posts and comments) from Firestore.
    """
    # Delete user's posts
    user_posts = post_service.get_posts_by_author(anonymous_id)
    for post in user_posts:
        post_service.delete_post(post['post_id'])

    # Delete user's comments
    user_comments = comment_service.get_comments_by_author(anonymous_id)
    for comment in user_comments:
        comment_service.delete_comment(comment['comment_id'])

    # Delete the user document
    users_collection = get_users_collection()
    doc_ref = users_collection.document(anonymous_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        return True
    return False
