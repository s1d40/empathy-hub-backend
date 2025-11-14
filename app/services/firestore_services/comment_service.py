import logging
import uuid
from typing import List, Optional, TYPE_CHECKING # Added TYPE_CHECKING
from firebase_admin import firestore
from app import schemas
from app.schemas.comment import CommentCreate, CommentUpdate
from app.schemas.enums import VoteTypeEnum, NotificationTypeEnum, NotificationStatusEnum # Import new enums
from app.schemas.notification import NotificationCreate # Import NotificationCreate directly
from app.services.firestore_services import user_service
from app.services.firestore_services import notification_service # Import notification_service
from app.services.firestore_services import post_service # Import post_service to get post author
if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_batch import BaseBatch # Added BaseBatch for type hinting

logger = logging.getLogger(__name__)

def get_posts_collection():
    return firestore.client().collection('posts')

def get_comment_post_mapping_collection():
    return firestore.client().collection('comment_post_mapping')

def delete_collection(coll_ref, batch_size, batch: Optional["BaseBatch"] = None):
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0
    for doc in docs:
        if batch:
            batch.delete(doc.reference)
        else:
            doc.reference.delete()
        deleted += 1
    if deleted >= batch_size:
        return delete_collection(coll_ref, batch_size, batch)

def _format_comment_response(comment: dict, users_map: dict) -> Optional[dict]:
    if not comment:
        return None
    author_id = comment.get('author_id')
    if author_id:
        author_data = users_map.get(author_id)
        comment['author'] = {
            "anonymous_id": author_id,
            "username": author_data.get('username') if author_data else "Unknown",
            "avatar_url": author_data.get('avatar_url') if author_data else None,
            "bio": author_data.get('bio') if author_data else None,
            "created_at": author_data.get('created_at') if author_data else None
        }
        comment.pop('author_id', None)
        comment.pop('author_username', None)
        comment.pop('author_avatar_url', None)
    if 'comment_id' in comment:
        comment['anonymous_comment_id'] = comment.pop('comment_id')
    return comment

def create_comment(post_id: str, comment_in: CommentCreate, author_id: str) -> dict:
    db = firestore.client()
    post_ref = get_posts_collection().document(post_id)
    post_doc = post_ref.get()
    if not post_doc.exists:
        raise ValueError("Post not found")
    
    post_author_id = post_doc.to_dict().get('author_id') # Get the post author ID

    author_data = user_service.get_user_by_anonymous_id(author_id)
    if not author_data:
        raise ValueError("Author not found")

    comment_id = str(uuid.uuid4())
    comment_ref = post_ref.collection('comments').document(comment_id)
    comment_data = {
        "comment_id": comment_id,
        "post_id": post_id,
        "content": comment_in.content,
        "author_id": author_id,
        "upvotes": 0,
        "downvotes": 0,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    mapping_ref = get_comment_post_mapping_collection().document(comment_id)

    @firestore.transactional
    def update_in_transaction(transaction, post_ref, comment_ref, comment_data, mapping_ref):
        post_snapshot = post_ref.get(transaction=transaction)
        current_comment_count = post_snapshot.get('comment_count') or 0
        transaction.set(comment_ref, comment_data)
        transaction.set(mapping_ref, {'post_id': post_id})
        transaction.update(post_ref, {'comment_count': current_comment_count + 1})

    transaction = db.transaction()
    update_in_transaction(transaction, post_ref, comment_ref, comment_data, mapping_ref)

    created_comment = comment_ref.get().to_dict()
    users_map = {author_id: author_data}

    logger.info(f"create_comment: Checking notification condition. Post Author ID: {post_author_id}, Comment Author ID: {author_id}")
    # Create notification for the post author if they are not the comment author
    if post_author_id and post_author_id != author_id:
        logger.info(f"create_comment: Condition met for notification creation. Recipient: {post_author_id}, Sender: {author_id}")
        notification_service.create_notification(
            notification_in=NotificationCreate(
                recipient_id=uuid.UUID(post_author_id),
                sender_id=uuid.UUID(author_id),
                notification_type=NotificationTypeEnum.NEW_COMMENT_ON_POST,
                content=f"{author_data.get('username', 'Someone')} commented on your post: '{comment_in.content[:50]}...'",
                resource_id=uuid.UUID(post_id),
                status=NotificationStatusEnum.UNREAD
            )
        )
    else:
        logger.info(f"create_comment: Condition NOT met for notification creation. Post Author ID: {post_author_id}, Comment Author ID: {author_id}")

    return _format_comment_response(created_comment, users_map)

def get_post_id_for_comment(comment_id: str) -> Optional[str]:
    mapping_doc = get_comment_post_mapping_collection().document(comment_id).get()
    if mapping_doc.exists:
        return mapping_doc.to_dict().get('post_id')
    return None

def get_comment_by_id(comment_id: str) -> Optional[dict]:
    post_id = get_post_id_for_comment(comment_id)
    if not post_id:
        return None
    return get_comment(post_id, comment_id)

def get_comment(post_id: str, comment_id: str) -> Optional[dict]:
    doc_ref = get_posts_collection().document(post_id).collection('comments').document(comment_id)
    doc = doc_ref.get()
    if doc.exists:
        comment_data = doc.to_dict()
        author_id = comment_data.get('author_id')
        users_data = user_service.get_users_by_anonymous_ids([author_id])
        users_map = {user['anonymous_id']: user for user in users_data}
        return _format_comment_response(comment_data, users_map)
    return None

def get_comments_for_post(post_id: str, skip: int = 0, limit: int = 100) -> List[dict]:
    comments_query = get_posts_collection().document(post_id).collection('comments').order_by('created_at', direction='DESCENDING')
    docs = list(comments_query.limit(limit).offset(skip).stream())

    if not docs:
        return []

    author_ids = list(set(doc.to_dict().get('author_id') for doc in docs))
    users_data = user_service.get_users_by_anonymous_ids(author_ids)
    users_map = {user['anonymous_id']: user for user in users_data}

    return [_format_comment_response(doc.to_dict(), users_map) for doc in docs]

def get_comments_by_author(author_id: str) -> List[dict]:
    # This is inefficient. A better solution would be a root-level 'comments' collection.
    all_posts = get_posts_collection().stream()
    comments = []
    for post in all_posts:
        comments_query = post.reference.collection('comments').where('author_id', '==', author_id)
        user_comments = comments_query.stream()
        for comment in user_comments:
            comments.append(comment.to_dict())
    
    if not comments:
        return []

    author_ids = list(set(comment.get('author_id') for comment in comments))
    users_data = user_service.get_users_by_anonymous_ids(author_ids)
    users_map = {user['anonymous_id']: user for user in users_data}

    return [_format_comment_response(comment, users_map) for comment in comments]

def update_comment(comment_id: str, comment_in: CommentUpdate) -> Optional[dict]:
    db = firestore.client()
    post_id = get_post_id_for_comment(comment_id)
    if not post_id:
        return None
    
    comment_ref = get_posts_collection().document(post_id).collection('comments').document(comment_id)

    @firestore.transactional
    def update_in_transaction(transaction):
        doc = comment_ref.get(transaction=transaction)
        if not doc.exists:
            return None

        update_data = comment_in.model_dump(exclude_unset=True)
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        transaction.update(comment_ref, update_data)
        return doc.to_dict().get('author_id')

    try:
        transaction = db.transaction()
        author_id = update_in_transaction(transaction)
        if author_id:
            comment_data = comment_ref.get().to_dict()
            users_data = user_service.get_users_by_anonymous_ids([author_id])
            users_map = {user['anonymous_id']: user for user in users_data}
            return _format_comment_response(comment_data, users_map)
        return None
    except Exception as e:
        # Log the exception e
        raise e

def delete_comment(comment_id: str, batch: Optional["BaseBatch"] = None) -> bool:
    post_id = get_post_id_for_comment(comment_id)
    if not post_id:
        return False
    
    post_ref = get_posts_collection().document(post_id)
    comment_ref = post_ref.collection('comments').document(comment_id)
    
    if not comment_ref.get().exists:
        return False

    # Delete subcollections (votes)
    delete_collection(comment_ref.collection('votes'), 50, batch)
    mapping_ref = get_comment_post_mapping_collection().document(comment_id)

    if batch:
        batch.delete(comment_ref)
        batch.delete(mapping_ref)
        # Decrement comment count in post (this needs to be handled carefully in a batch)
        # For now, we'll assume the calling function (delete_all_comments_by_author)
        # will handle the post comment count update if needed, or we'll rely on a Cloud Function.
        # Direct decrement in a batch without reading the current value first is problematic.
        # For simplicity in this batch context, we'll omit the comment_count update here.
        # A more robust solution would involve a distributed counter or a Cloud Function trigger.
    else:
        # Original transactional logic for standalone deletion
        db = firestore.client()
        @firestore.transactional
        def delete_in_transaction(transaction, post_ref, comment_ref, mapping_ref):
            post_snapshot = post_ref.get(transaction=transaction)
            current_comment_count = post_snapshot.get('comment_count') or 0
            transaction.delete(comment_ref)
            transaction.delete(mapping_ref)
            transaction.update(post_ref, {'comment_count': max(0, current_comment_count - 1)})

        transaction = db.transaction()
        delete_in_transaction(transaction, post_ref, comment_ref, mapping_ref)
    return True

def delete_all_comments_by_author(author_id: str, batch: Optional["BaseBatch"] = None) -> int:
    """
    Deletes all comments by a specific author.
    If a batch is provided, the delete operations are added to the batch.
    Otherwise, it commits immediately (though this function is intended to be called with a batch).
    """
    deleted_count = 0
    # Get all comments by the author (this uses the inefficient get_comments_by_author)
    comments_to_delete = get_comments_by_author(author_id)
    
    for comment_data in comments_to_delete:
        comment_id = comment_data.get('anonymous_comment_id')
        if comment_id:
            # Pass the batch to delete_comment
            if delete_comment(comment_id, batch):
                deleted_count += 1
    return deleted_count
def vote_on_comment(comment_id: str, user_id: str, vote_type: VoteTypeEnum) -> Optional[dict]:
    post_id = get_post_id_for_comment(comment_id)
    if not post_id:
        raise ValueError("Comment not found")

    db = firestore.client()
    comment_ref = get_posts_collection().document(post_id).collection('comments').document(comment_id)
    vote_ref = comment_ref.collection('votes').document(user_id)

    @firestore.transactional
    def update_in_transaction(transaction, comment_ref, vote_ref):
        comment_snapshot = comment_ref.get(transaction=transaction)
        if not comment_snapshot.exists:
            raise ValueError("Comment not found")

        vote_snapshot = vote_ref.get(transaction=transaction)
        current_upvotes = comment_snapshot.get('upvotes') or 0
        current_downvotes = comment_snapshot.get('downvotes') or 0
        existing_vote_type = vote_snapshot.get('vote_type') if vote_snapshot.exists else None

        upvote_change = 0
        downvote_change = 0

        if existing_vote_type == vote_type.value: # Unvoting
            transaction.delete(vote_ref)
            if vote_type == VoteTypeEnum.UPVOTE:
                upvote_change = -1
            else:
                downvote_change = -1
        elif existing_vote_type: # Changing vote
            transaction.set(vote_ref, {'vote_type': vote_type.value})
            if vote_type == VoteTypeEnum.UPVOTE:
                upvote_change = 1
                downvote_change = -1
            else:
                upvote_change = -1
                downvote_change = 1
        else: # New vote
            transaction.set(vote_ref, {'vote_type': vote_type.value})
            if vote_type == VoteTypeEnum.UPVOTE:
                upvote_change = 1
            else:
                downvote_change = 1
        
        transaction.update(comment_ref, {
            'upvotes': current_upvotes + upvote_change,
            'downvotes': current_downvotes + downvote_change
        })
        return comment_snapshot.to_dict().get('author_id')

    transaction = db.transaction()
    author_id = update_in_transaction(transaction, comment_ref, vote_ref)

    comment_data = comment_ref.get().to_dict()
    users_data = user_service.get_users_by_anonymous_ids([author_id])
    users_map = {user['anonymous_id']: user for user in users_data}
    return _format_comment_response(comment_data, users_map)
