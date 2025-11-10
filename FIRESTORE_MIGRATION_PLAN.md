# Firestore Migration Plan: Empathy Hub Backend

This document outlines the plan for migrating the Empathy Hub backend from its current PostgreSQL database setup to a serverless architecture primarily utilizing Google Cloud Firestore. This migration aims to optimize costs for an early-stage application by leveraging a pay-per-use model and automatic scaling.

**Important Note:** This plan focuses on creating a new, serverless version of the backend. The existing PostgreSQL-based backend will **NOT** be erased and will be kept for future reference and potential use.

---

## High-Level Migration Plan

### Phase 1: Database Migration to Google Cloud Firestore

The core of this migration involves moving from a relational SQL database (PostgreSQL) to a NoSQL document database (Firestore).

*   **Recommendation**: Google Cloud Firestore
    *   **Rationale**: Firestore is a fully managed, serverless, NoSQL document database. Its pay-per-use model (based on reads, writes, deletes, and storage) is ideal for variable traffic, making it highly cost-effective for early-stage applications. Its real-time capabilities also offer significant advantages for features like chat, potentially simplifying the existing WebSocket implementation.

*   **Action Steps**:
    1.  **Data Model Redesign for Firestore**:
        *   Analyze the existing PostgreSQL schema (`app/db/models/`).
        *   Design a new document-based data model suitable for Firestore. This involves defining collections and documents, considering how relationships (one-to-many, many-to-many) will be represented in a NoSQL context (e.g., denormalization, subcollections, references).
        *   Key models to redesign: `User`, `Post`, `Comment`, `ChatRoom`, `ChatMessage`, `ChatRequest`, `UserRelationship`, `Report`.
    2.  **Data Migration Script Development**:
        *   Create a Python script (or similar) that can connect to the existing PostgreSQL database.
        *   The script will read data from PostgreSQL tables.
        *   It will transform this data into the new Firestore document structure.
        *   Finally, it will write the transformed data into a new Google Cloud Firestore instance. This script will be crucial for populating the new database with existing data.

### Phase 2: Application Logic Adaptation for Firestore

The current backend logic is tightly coupled with SQLAlchemy. This phase involves refactoring the data access layer to interact with Firestore.

*   **Recommendation**: Replace the `app/crud` layer with a new data access layer that directly interacts with Firestore.

*   **Action Steps**:
    1.  **Develop a New Data Access Layer (`app/services/firestore_services`)**:
        *   Create a new directory (e.g., `app/services/firestore_services`).
        *   Within this directory, create modules (e.g., `user_service.py`, `post_service.py`, `chat_service.py`, etc.) that encapsulate all Firestore interactions for each entity.
        *   These new services will replace the functionality of the existing `app/crud` modules. They will handle creating, reading, updating, and deleting documents in Firestore collections.
    2.  **Update API Endpoints (`app/api/v1/endpoints/`)**:
        *   Modify all existing API endpoint functions in `app/api/v1/endpoints/` (e.g., `users.py`, `posts.py`, `chat.py`, `comments.py`, `user_actions.py`, `reports.py`).
        *   Replace calls to `crud.*` functions with calls to the newly created `app/services/firestore_services.*` functions.
        *   Adjust input/output schemas (`app/schemas/`) as necessary to align with Firestore's data structures and the new service layer's expectations.
    3.  **Refactor Chat Backend for Real-time (Optional but Recommended)**:
        *   The current WebSocket implementation (`app/api/v1/endpoints/chat.py` and `app/core/chat_manager.py`) can be simplified.
        *   Leverage Firestore's real-time listeners directly on the client-side (frontend) to subscribe to chat message collections. This can reduce the complexity of the backend WebSocket server, potentially allowing for a simpler backend implementation (e.g., using Cloud Functions for message processing rather than a long-running WebSocket server).
        *   If a backend WebSocket server is still desired (e.g., for complex server-side logic or broadcasting), ensure it integrates seamlessly with Firestore.

### Phase 3: Deployment to Google Cloud Run

The refactored FastAPI application will be deployed to a serverless container platform.

*   **Recommendation**: Google Cloud Run
    *   **Rationale**: Cloud Run is a fully managed compute platform that enables you to run stateless containers via web requests or Pub/Sub events. It automatically scales your application up and down, even to zero instances, meaning you only pay for the compute resources consumed during request processing. This aligns perfectly with the cost-efficiency goal.

*   **Action Steps**:
    1.  **Optimize Containerization**:
        *   Review and optimize the existing `Dockerfile` for efficiency and smaller image size.
        *   Ensure the container is stateless, as required by Cloud Run.
        *   Update dependencies to reflect the new Firestore client libraries.
    2.  **Deploy to Cloud Run**:
        *   Build the Docker image and push it to Google Container Registry (GCR) or Artifact Registry.
        *   Create a new Cloud Run service.
        *   Configure the Cloud Run service with the necessary environment variables (e.g., Google Cloud Project ID, any Firestore-specific settings).
        *   Set up appropriate IAM roles and permissions for the Cloud Run service to access Firestore.
    3.  **Implement CI/CD Pipeline**:
        *   Set up a Continuous Integration/Continuous Deployment (CI/CD) pipeline using Google Cloud Build.
        *   This pipeline will automatically build the Docker image, run tests, and deploy new versions of the Cloud Run service whenever changes are pushed to the main branch of your repository.

---

## Important Considerations

*   **Preservation of SQL Backend**: The existing PostgreSQL database and the current backend code will remain untouched. This provides a fallback and a reference for the original implementation.
*   **Cost Monitoring**: Continuously monitor Firestore and Cloud Run usage and costs to ensure the serverless approach remains cost-effective as the application scales.
*   **Security**: Ensure proper IAM roles, service accounts, and API keys are configured for secure access between Cloud Run and Firestore.
*   **Testing**: Thoroughly test all migrated functionalities, especially data integrity and real-time features, after each phase of the migration.

This plan provides a structured approach to transitioning the Empathy Hub backend to a modern, scalable, and cost-efficient serverless architecture on Google Cloud.
