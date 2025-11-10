import uuid
from typing import List, Optional
from firebase_admin import firestore
from app.schemas.post import PostCreate, PostUpdate
from app.schemas.enums import VoteTypeEnum
from app.services.firestore_services import user_service

# This service replaces the functionality of crud/crud_post.py for a Firestore database.

def get_posts_collection():
    """Returns the 'posts' collection reference, ensuring the client is requested after initialization."""
    return firestore.client().collection('posts')

def _format_post(post_dict: dict) -> dict:
    """
    Formats a post dictionary to match the PostRead schema.
    """
    if not post_dict:
        return None
    post_dict['anonymous_post_id'] = post_dict.pop('post_id')
    post_dict['author'] = {
        'anonymous_id': post_dict.pop('author_id'),
        'username': post_dict.pop('author_username'),
        'avatar_url': post_dict.pop('author_avatar_url')
    }
    return post_dict

def delete_collection(coll_ref, batch_size):
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        doc.reference.delete()
        deleted = deleted + 1

    if deleted >= batch_size:
        return delete_collection(coll_ref, batch_size)

def create_post(post_in: PostCreate, author_id: str) -> dict:
    """
    Creates a new post document in Firestore.
    """
    posts_collection = get_posts_collection()
    post_id = str(uuid.uuid4())
    author_data = user_service.get_user_by_anonymous_id(author_id)
    if not author_data:
        raise ValueError("Author not found")

    post_data = {
        "post_id": post_id,
        "title": post_in.title,
        "content": post_in.content,
        "author_id": author_id,
        "author_username": author_data.get('username'),
        "author_avatar_url": author_data.get('avatar_url'),
        "upvotes": 0,
        "downvotes": 0,
        "comment_count": 0,
        "is_active": True,
        "is_edited": False,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    
    doc_ref = posts_collection.document(post_id)
    doc_ref.set(post_data)

    # Retrieve the document to get server-generated timestamps
    created_doc = doc_ref.get()
    if not created_doc.exists:
        raise ValueError("Failed to create post")

    return _format_post(created_doc.to_dict())

def get_post(post_id: str) -> Optional[dict]:
    """
    Retrieves a post document by its ID.
    """
    posts_collection = get_posts_collection()
    doc_ref = posts_collection.document(post_id)
    doc = doc_ref.get()
    if doc.exists:
        return _format_post(doc.to_dict())
    return None

def get_posts(skip: int = 0, limit: int = 100) -> List[dict]:
    """
    Retrieves a list of posts with pagination.
    """
    posts_collection = get_posts_collection()
    docs = posts_collection.order_by('created_at', direction='DESCENDING').limit(limit).offset(skip).stream()
    return [_format_post(doc.to_dict()) for doc in docs]

def get_posts_by_author(author_id: str) -> List[dict]:
    """
    Retrieves all posts by a specific author.
    """
    posts_collection = get_posts_collection()
    docs = posts_collection.where('author_id', '==', author_id).stream()
    return [doc.to_dict() for doc in docs]

def update_post(post_id: str, post_in: PostUpdate) -> Optional[dict]:
    """
    Updates a post document in Firestore.
    """
    posts_collection = get_posts_collection()
    doc_ref = posts_collection.document(post_id)
    doc = doc_ref.get()
    if not doc.exists:
        return None

    update_data = post_in.model_dump(exclude_unset=True)
    update_data['updated_at'] = firestore.SERVER_TIMESTAMP
    if 'content' in update_data:
        update_data['is_edited'] = True

    doc_ref.update(update_data)
    return _format_post(doc_ref.get().to_dict())

def delete_post(post_id: str) -> bool:
    """
    Deletes a post document and its subcollections from Firestore.
    """
    posts_collection = get_posts_collection()
    post_ref = posts_collection.document(post_id)
    
    # Delete subcollections
    comments_ref = post_ref.collection('comments')
    votes_ref = post_ref.collection('votes')
    delete_collection(comments_ref, 50)
    delete_collection(votes_ref, 50)

    # Delete the post document itself
    post_ref.delete()
    return True

def vote_on_post(post_id: str, user_id: str, vote_type: VoteTypeEnum) -> Optional[dict]:
    """
    Processes a vote on a post.
    """
    db = firestore.client()
    posts_collection = get_posts_collection()
    post_ref = posts_collection.document(post_id)
    vote_ref = post_ref.collection('votes').document(user_id)

    @firestore.transactional
    def update_in_transaction(transaction, post_ref, vote_ref):
        post_snapshot = post_ref.get(transaction=transaction)
        if not post_snapshot.exists:
            raise ValueError("Post not found")

        vote_snapshot = vote_ref.get(transaction=transaction)

        current_upvotes = post_snapshot.get('upvotes')
        current_downvotes = post_snapshot.get('downvotes')

        if vote_snapshot.exists:
            existing_vote_type = vote_snapshot.get('vote_type')
            if existing_vote_type == vote_type.value:
                # Unvoting
                transaction.delete(vote_ref)
                if vote_type == VoteTypeEnum.UPVOTE:
                    transaction.update(post_ref, {'upvotes': current_upvotes - 1})
                else:
                    transaction.update(post_ref, {'downvotes': current_downvotes - 1})
            else:
                # Changing vote
                transaction.set(vote_ref, {'vote_type': vote_type.value})
                if vote_type == VoteTypeEnum.UPVOTE: # Was downvote, now upvote
                    transaction.update(post_ref, {
                        'upvotes': current_upvotes + 1,
                        'downvotes': current_downvotes - 1
                    })
                else: # Was upvote, now downvote
                    transaction.update(post_ref, {
                        'upvotes': current_upvotes - 1,
                        'downvotes': current_downvotes + 1
                    })
        else:
            # New vote
            transaction.set(vote_ref, {'vote_type': vote_type.value})
            if vote_type == VoteTypeEnum.UPVOTE:
                transaction.update(post_ref, {'upvotes': current_upvotes + 1})
            else:
                transaction.update(post_ref, {'downvotes': current_downvotes + 1})

    transaction = db.transaction()
    update_in_transaction(transaction, post_ref, vote_ref)

    return _format_post(post_ref.get().to_dict())
