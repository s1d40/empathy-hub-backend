import os
import sys
import asyncio

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings
import firebase_admin
from firebase_admin import credentials as firebase_credentials
from google.auth import credentials as google_credentials

def initialize_firebase():
    print("Initializing Firebase Admin SDK for script...")
    if not firebase_admin._apps:
        try:
            if settings.FIRESTORE_EMULATOR_HOST:
                cred = google_credentials.AnonymousCredentials()
                firebase_admin.initialize_app(cred, {'projectId': settings.GCP_PROJECT_ID})
                print("Firebase initialized with EMULATOR.")
            else:
                cred = firebase_credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {'projectId': settings.GCP_PROJECT_ID})
                print("Firebase initialized with Application Default Credentials.")
        except Exception as e:
            print(f"Firebase initialization failed: {e}")
            sys.exit(1)
    else:
        print("Firebase app already initialized.")

async def cleanup_orphaned_posts():
    from app.services.firestore_services import post_service, user_service

    print("Starting cleanup of orphaned posts...")
    all_posts = post_service.get_posts(limit=1000) # Adjust limit as needed
    orphaned_posts_count = 0
    for post in all_posts:
        author_id = post.get('author', {}).get('anonymous_id')
        if not author_id:
            author_id = post.get('author_id')

        if author_id:
            user = user_service.get_user_by_anonymous_id(author_id)
            if not user:
                post_id_to_delete = post.get('anonymous_post_id') or post.get('post_id')
                print(f"Found orphaned post with ID: {post_id_to_delete} from author: {author_id}. Deleting...")
                post_service.delete_post(post_id_to_delete)
                orphaned_posts_count += 1
        else:
            post_id_to_skip = post.get('anonymous_post_id') or post.get('post_id')
            print(f"Post with ID: {post_id_to_skip} has no author information. Skipping.")

    print(f"Cleanup finished. Deleted {orphaned_posts_count} orphaned posts.")

if __name__ == "__main__":
    initialize_firebase()
    asyncio.run(cleanup_orphaned_posts())
