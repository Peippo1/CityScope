from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Protocol

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .agent.schemas import InvestigationRequest, InvestigationResult
from .auth import CurrentUser


class SavedInvestigationCreate(BaseModel):
    request: InvestigationRequest
    result: InvestigationResult


class SavedInvestigation(BaseModel):
    id: str
    question: str = Field(max_length=500)
    selected_h3_cells: list[str] = Field(max_length=50)
    status: str
    summary: str = Field(max_length=1200)
    dataset_snapshot_id: str | None = None
    dataset_name: str | None = None
    historical_evidence: list[dict] = Field(default_factory=list)
    created_at: datetime


class InvestigationStore(Protocol):
    def create(self, user: CurrentUser, payload: SavedInvestigationCreate) -> SavedInvestigation: ...
    def list(self, user: CurrentUser) -> list[SavedInvestigation]: ...
    def get(self, user: CurrentUser, investigation_id: str) -> SavedInvestigation | None: ...
    def delete(self, user: CurrentUser, investigation_id: str) -> bool: ...


def _record(payload: SavedInvestigationCreate, investigation_id: str | None = None) -> SavedInvestigation:
    result = payload.result
    historical_evidence = [item.model_dump(mode="json") for item in result.evidence if item.source == "city_data"]
    return SavedInvestigation(
        id=investigation_id or str(uuid.uuid4()),
        question=payload.request.question,
        selected_h3_cells=payload.request.context.selected_h3_cells,
        status=result.status,
        summary=result.answer,
        dataset_snapshot_id=result.dataset.snapshot_id if result.dataset else None,
        dataset_name=result.dataset.dataset_name if result.dataset else None,
        historical_evidence=historical_evidence,
        created_at=datetime.now(timezone.utc),
    )


class InMemoryInvestigationStore:
    """Test double; production uses Firestore and never falls back to process memory."""
    def __init__(self) -> None:
        self.records: dict[str, tuple[str, SavedInvestigation]] = {}

    def create(self, user: CurrentUser, payload: SavedInvestigationCreate) -> SavedInvestigation:
        record = _record(payload)
        self.records[record.id] = (user.uid, record)
        return record

    def list(self, user: CurrentUser) -> list[SavedInvestigation]:
        return sorted((record for owner, record in self.records.values() if owner == user.uid), key=lambda record: record.created_at, reverse=True)

    def get(self, user: CurrentUser, investigation_id: str) -> SavedInvestigation | None:
        item = self.records.get(investigation_id)
        return item[1] if item and item[0] == user.uid else None

    def delete(self, user: CurrentUser, investigation_id: str) -> bool:
        record = self.get(user, investigation_id)
        if not record:
            return False
        del self.records[investigation_id]
        return True


class FirestoreInvestigationStore:
    collection_name = "saved_investigations"

    def __init__(self) -> None:
        try:
            from firebase_admin import firestore
        except ImportError as error:
            raise RuntimeError("firebase-admin must be installed to save investigations") from error
        self.client = firestore.client()

    def create(self, user: CurrentUser, payload: SavedInvestigationCreate) -> SavedInvestigation:
        document = self.client.collection(self.collection_name).document()
        record = _record(payload, document.id)
        document.set({"owner_uid": user.uid, **record.model_dump(mode="json")})
        return record

    def list(self, user: CurrentUser) -> list[SavedInvestigation]:
        documents = self.client.collection(self.collection_name).where("owner_uid", "==", user.uid).stream()
        return sorted((SavedInvestigation.model_validate(document.to_dict()) for document in documents), key=lambda record: record.created_at, reverse=True)

    def get(self, user: CurrentUser, investigation_id: str) -> SavedInvestigation | None:
        document = self.client.collection(self.collection_name).document(investigation_id).get()
        payload = document.to_dict() if document.exists else None
        return SavedInvestigation.model_validate(payload) if payload and payload.get("owner_uid") == user.uid else None

    def delete(self, user: CurrentUser, investigation_id: str) -> bool:
        document = self.client.collection(self.collection_name).document(investigation_id)
        payload = document.get().to_dict()
        if not payload or payload.get("owner_uid") != user.uid:
            return False
        document.delete()
        return True


def get_history_store() -> InvestigationStore:
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise HTTPException(status_code=503, detail="Saved investigations are not configured")
    try:
        return FirestoreInvestigationStore()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Saved investigations are unavailable") from None
