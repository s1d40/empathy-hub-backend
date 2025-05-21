import uuid
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.db import models
from app import schemas # This will provide ChatRequestCreate, ChatRequestUpdate via __init__.py
from app.crud.base import CRUDBase
from app.schemas.enums import ChatRequestStatusEnum
from sqlalchemy import func # For func.now()


class CRUDChatRequest(CRUDBase[models.ChatRequest, schemas.ChatRequestCreate, schemas.ChatRequestUpdate]):
    def get_by_anonymous_id(self, db: Session, *, anonymous_request_id: uuid.UUID) -> Optional[models.ChatRequest]:
        return db.query(models.ChatRequest).options(
            joinedload(models.ChatRequest.requester),
            joinedload(models.ChatRequest.requestee)
        ).filter(models.ChatRequest.anonymous_request_id == anonymous_request_id).first()

    def create_request(
        self,
        db: Session,
        *,
        request_in: schemas.ChatRequestCreate,
        requester_anonymous_id: uuid.UUID
    ) -> models.ChatRequest:
        existing_pending = db.query(models.ChatRequest).filter(
            models.ChatRequest.requester_anonymous_id == requester_anonymous_id,
            models.ChatRequest.requestee_anonymous_id == request_in.requestee_anonymous_id,
            models.ChatRequest.status == ChatRequestStatusEnum.PENDING
        ).first()
        if existing_pending:
            return existing_pending

        db_obj = models.ChatRequest(
            requester_anonymous_id=requester_anonymous_id,
            requestee_anonymous_id=request_in.requestee_anonymous_id,
            initial_message=request_in.initial_message,
            status=ChatRequestStatusEnum.PENDING
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_pending_requests_for_user(
        self, db: Session, *, user_anonymous_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> List[models.ChatRequest]:
        """Gets pending requests where the given user is the requestee."""
        return (
            db.query(models.ChatRequest)
            .filter(
                models.ChatRequest.requestee_anonymous_id == user_anonymous_id,
                models.ChatRequest.status == ChatRequestStatusEnum.PENDING
            )
            .options(joinedload(models.ChatRequest.requester), joinedload(models.ChatRequest.requestee))
            .order_by(models.ChatRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_status(
        self, db: Session, *, db_obj: models.ChatRequest, status: ChatRequestStatusEnum
    ) -> models.ChatRequest:
        db_obj.status = status
        db_obj.responded_at = func.now() # Use func.now() for database-side timestamp
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

chat_request = CRUDChatRequest(models.ChatRequest)