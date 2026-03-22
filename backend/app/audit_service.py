from __future__ import annotations

from app.auth import utc_now_iso
from app.models import AuditEventsResponse
from app.storage import AppStorage


class AuditService:
    def __init__(self, storage: AppStorage) -> None:
        self._storage = storage

    def list_events(self, limit: int = 50) -> AuditEventsResponse:
        return AuditEventsResponse(
            generated_at=utc_now_iso(),
            events=self._storage.list_audit_events(limit=limit),
        )
