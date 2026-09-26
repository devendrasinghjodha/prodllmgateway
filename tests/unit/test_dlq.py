import pytest
from app.queue.dlq import DeadLetterQueue


def test_dlq_push_and_retrieval():
    dlq = DeadLetterQueue()
    item = dlq.push(
        payload={"model": "gemini", "messages": [{"role": "user", "content": "hello"}]},
        error_message="503 Service Unavailable",
        error_type="ProviderUnavailable",
        team_id="team_engineering",
    )
    assert item.id.startswith("dlq_")
    assert item.status == "failed"

    # List items
    items = dlq.list_items()
    assert len(items) == 1
    assert items[0].id == item.id

    # Mark replayed
    dlq.mark_replayed(item.id)
    assert dlq.get_item(item.id).status == "replayed"
    assert dlq.get_item(item.id).attempts == 2

    # Dismiss item
    dismissed = dlq.dismiss(item.id)
    assert dismissed is True
    assert len(dlq.list_items()) == 0
