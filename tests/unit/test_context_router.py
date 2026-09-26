import pytest
from app.routing.context_router import ContextLengthPolicy
from app.providers.base import ChatRequest, ChatMessage
from app.routing.router import router


def test_context_length_routing():
    policy = ContextLengthPolicy()
    available = router.get_all_providers()

    # Short prompt (< 2000 tokens)
    short_req = ChatRequest(
        model="auto",
        messages=[ChatMessage(role="user", content="Hi there!")],
    )
    ordered_short = policy.select_providers(short_req, available)
    assert len(ordered_short) > 0
    assert ordered_short[0].name == "agnes"

    # Extremely long prompt (> 8000 tokens)
    long_content = "This is an extensive document paragraph. " * 1000
    long_req = ChatRequest(
        model="auto",
        messages=[ChatMessage(role="user", content=long_content)],
    )
    ordered_long = policy.select_providers(long_req, available)
    assert len(ordered_long) > 0
    assert ordered_long[0].name == "gemini"
