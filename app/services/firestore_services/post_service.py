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

def _format_post(post_dict: dict, users_map: dict) -> dict:
    """
    Formats a post dictionary to match the PostRead schema.
    """
    if not post_dict:
        return None
    post_dict['anonymous_post_id'] = post_dict.pop('post_id')
    author_id = post_dict.pop('author_id')
    author_data = users_map.get(author_id)
    post_dict['author'] = {
        'anonymous_id': author_id,
        'username': author_data.get('username') if author_data else "Unknown",
        'avatar_url': author_data.get('avatar_url') if author_data else None
    }
    post_dict.pop('author_username', None)
    post_dict.pop('author_avatar_url', None)
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

    users_map = {author_id: author_data}
    return _format_post(created_doc.to_dict(), users_map)

def get_post(post_id: str) -> Optional[dict]:
    """
    Retrieves a post document by its ID.
    """
    posts_collection = get_posts_collection()
    doc_ref = posts_collection.document(post_id)
    doc = doc_ref.get()
    if doc.exists:
        post_data = doc.to_dict()
        author_id = post_data.get('author_id')
        users_data = user_service.get_users_by_anonymous_ids([author_id])
        users_map = {user['anonymous_id']: user for user in users_data}
        return _format_post(post_data, users_map)
    return None

def get_posts(skip: int = 0, limit: int = 100) -> List[dict]:
    """
    Retrieves a list of posts with pagination.
    """
    posts_collection = get_posts_collection()
    query = posts_collection.order_by('created_at', direction='DESCENDING').limit(limit).offset(skip)
    docs = list(query.stream())
    
    if not docs:
        return []

    post_list = []
    for doc in docs:
        post_data = doc.to_dict()
        
        # TODO: This is not performant. For each post, we are making a new query to get the comment count.
        # A better approach would be to use a distributed counter.
        comments_collection = doc.reference.collection('comments')
        # Use aggregate query to count comments more efficiently
        aggregation_query = comments_collection.count()
        query_result = aggregation_query.get()
        comment_count = query_result[0][0].value if query_result else 0
        
        post_data['comment_count'] = comment_count
        post_list.append(post_data)

    author_ids = list(set(post.get('author_id') for post in post_list))
    users_data = user_service.get_users_by_anonymous_ids(author_ids)
    users_map = {user['anonymous_id']: user for user in users_data}

    return [_format_post(post, users_map) for post in post_list]

def get_posts_by_author(author_id: str) -> List[dict]:
    """
    Retrieves all posts by a specific author.
    """
    posts_collection = get_posts_collection()
    docs = list(posts_collection.where('author_id', '==', author_id).stream())

    if not docs:
        return []

    author_ids = list(set(doc.to_dict().get('author_id') for doc in docs))
    users_data = user_service.get_users_by_anonymous_ids(author_ids)
    users_map = {user['anonymous_id']: user for user in users_data}

    return [_format_post(doc.to_dict(), users_map) for doc in docs]

def update_post(post_id: str, post_in: PostUpdate) -> Optional[dict]:
    """
    Updates a post document in Firestore using a transaction.
    """
    db = firestore.client()
    posts_collection = get_posts_collection()
    post_ref = posts_collection.document(post_id)

    @firestore.transactional
    def update_in_transaction(transaction):
        doc = post_ref.get(transaction=transaction)
        if not doc.exists:
            return None

        update_data = post_in.model_dump(exclude_unset=True)
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        if 'content' in update_data or 'title' in update_data:
            update_data['is_edited'] = True

        transaction.update(post_ref, update_data)
        return doc.to_dict().get('author_id')

    try:
        transaction = db.transaction()
        author_id = update_in_transaction(transaction)
        if author_id:
            post_data = post_ref.get().to_dict()
            users_data = user_service.get_users_by_anonymous_ids([author_id])
            users_map = {user['anonymous_id']: user for user in users_data}
            return _format_post(post_data, users_map)
        return None
    except Exception as e:
        # Log the exception e
        raise e

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

def delete_all_posts_by_author(author_id: str) -> int:
    """
    Deletes all posts by a specific author, including their subcollections.
    """
    posts_collection = get_posts_collection()
    query = posts_collection.where('author_id', '==', author_id).stream()
    
    deleted_count = 0
    for doc in query:
        post_id = doc.id
        delete_post(post_id) # Use the existing delete_post to handle subcollections
        deleted_count += 1
    return deleted_count

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
        
        return post_snapshot.to_dict().get('author_id')

    transaction = db.transaction()
    author_id = update_in_transaction(transaction, post_ref, vote_ref)

    post_data = post_ref.get().to_dict()
    users_data = user_service.get_users_by_anonymous_ids([author_id])
    users_map = {user['anonymous_id']: user for user in users_data}
    return _format_post(post_data, users_map)
