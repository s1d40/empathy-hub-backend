import uuid
from typing import List, Optional
from firebase_admin import firestore
from app.schemas.comment import CommentCreate, CommentUpdate
from app.schemas.enums import VoteTypeEnum
from app.services.firestore_services import user_service

def get_posts_collection():
    return firestore.client().collection('posts')

def get_comment_post_mapping_collection():
    return firestore.client().collection('comment_post_mapping')

def delete_collection(coll_ref, batch_size):
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0
    for doc in docs:
        doc.reference.delete()
        deleted += 1
    if deleted >= batch_size:
        return delete_collection(coll_ref, batch_size)

def _format_comment_response(comment: dict) -> Optional[dict]:
    if not comment:
        return None
    author_id = comment.get('author_id')
    if author_id:
        author_data = user_service.get_user_by_anonymous_id(author_id)
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
    if not post_ref.get().exists:
        raise ValueError("Post not found")

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
    return _format_comment_response(created_comment)

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
    return _format_comment_response(doc.to_dict())

def get_comments_for_post(post_id: str, skip: int = 0, limit: int = 100) -> List[dict]:
    comments_query = get_posts_collection().document(post_id).collection('comments').order_by('created_at', direction='DESCENDING')
    docs = comments_query.limit(limit).offset(skip).stream()
    return [_format_comment_response(doc.to_dict()) for doc in docs]

def get_comments_by_author(author_id: str) -> List[dict]:
    # This is inefficient. A better solution would be a root-level 'comments' collection.
    all_posts = get_posts_collection().stream()
    comments = []
    for post in all_posts:
        comments_query = post.reference.collection('comments').where('author_id', '==', author_id)
        user_comments = comments_query.stream()
        for comment in user_comments:
            comments.append(comment.to_dict())
    return comments

def update_comment(comment_id: str, comment_in: CommentUpdate) -> Optional[dict]:
    post_id = get_post_id_for_comment(comment_id)
    if not post_id:
        return None
    doc_ref = get_posts_collection().document(post_id).collection('comments').document(comment_id)
    if not doc_ref.get().exists:
        return None
    update_data = comment_in.model_dump(exclude_unset=True)
    update_data['updated_at'] = firestore.SERVER_TIMESTAMP
    doc_ref.update(update_data)
    return get_comment(post_id, comment_id)

def delete_comment(comment_id: str) -> bool:
    post_id = get_post_id_for_comment(comment_id)
    if not post_id:
        return False
    
    db = firestore.client()
    post_ref = get_posts_collection().document(post_id)
    comment_ref = post_ref.collection('comments').document(comment_id)
    
    if not comment_ref.get().exists:
        return False

    delete_collection(comment_ref.collection('votes'), 50)
    mapping_ref = get_comment_post_mapping_collection().document(comment_id)

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

    transaction = db.transaction()
    update_in_transaction(transaction, comment_ref, vote_ref)
    return get_comment(post_id, comment_id)
