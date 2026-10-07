import datetime
import uuid
from typing import Any

from pydantic import BaseModel, Field


class DLQItem(BaseModel):
    id: str = Field(default_factory=lambda: f"dlq_{uuid.uuid4().hex[:12]}")
    original_request_id: str | None = None
    team_id: str | None = None
    endpoint: str = "/v1/chat/completions"
    payload: dict[str, Any]
    error_message: str
    error_type: str
    attempts: int = 1
    status: str = "failed"  # 'failed', 'replayed', 'dismissed'
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    last_attempted_at: str | None = None


class DeadLetterQueue:
    """
    Stores requests that encountered fatal upstream failures after all retry & fallback attempts.
    Allows auditing, debugging, and offline manual or automated replay.
    """
    def __init__(self):
        self._queue: dict[str, DLQItem] = {}

    def push(
        self,
        payload: dict[str, Any],
        error_message: str,
        error_type: str = "ProviderError",
        original_request_id: str | None = None,
        team_id: str | None = None,
        endpoint: str = "/v1/chat/completions",
    ) -> DLQItem:
        item = DLQItem(
            original_request_id=original_request_id,
            team_id=team_id,
            endpoint=endpoint,
            payload=payload,
            error_message=error_message,
            error_type=error_type,
        )
        self._queue[item.id] = item
        return item

    def list_items(self, status: str | None = None, limit: int = 50) -> list[DLQItem]:
        items = list(self._queue.values())
        if status:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda x: x.created_at, reverse=True)[:limit]

    def get_item(self, item_id: str) -> DLQItem | None:
        return self._queue.get(item_id)

    def mark_replayed(self, item_id: str):
        if item_id in self._queue:
            self._queue[item_id].status = "replayed"
            self._queue[item_id].last_attempted_at = datetime.datetime.utcnow().isoformat()
            self._queue[item_id].attempts += 1

    def dismiss(self, item_id: str) -> bool:
        if item_id in self._queue:
            del self._queue[item_id]
            return True
        return False

    def clear(self):
        self._queue.clear()


# Global Singleton DLQ
dlq_manager = DeadLetterQueue()
