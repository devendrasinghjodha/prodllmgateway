import pytest
from app.cache.redis import generate_cache_key, CacheManager
from app.providers.base import ChatRequest, ChatMessage, ChatResponse, ChatChoice, ChatChoiceMessage, Usage


def test_deterministic_cache_key():
    req1 = ChatRequest(
        model="gemini",
        messages=[ChatMessage(role="user", content="Explain TCP in simple terms")],
        temperature=0.7,
    )
    req2 = ChatRequest(
        model="gemini",
        messages=[ChatMessage(role="user", content="Explain TCP in simple terms")],
        temperature=0.7,
    )
    req_diff = ChatRequest(
        model="gemini",
        messages=[ChatMessage(role="user", content="Explain UDP in simple terms")],
        temperature=0.7,
    )

    key1 = generate_cache_key(req1)
    key2 = generate_cache_key(req2)
    key_diff = generate_cache_key(req_diff)

    assert key1 == key2
    assert key1 != key_diff


@pytest.mark.asyncio
async def test_cache_manager_in_memory():
    mgr = CacheManager(r_client=None)
    key = "test:key:123"
    resp = ChatResponse(
        id="chatcmpl-test",
        model="gemini",
        choices=[ChatChoice(index=0, message=ChatChoiceMessage(role="assistant", content="Hello!"))],
        usage=Usage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
    )

    # Initially None
    assert await mgr.get_cached_response(key) is None

    # Set and Get
    await mgr.set_cached_response(key, resp, ttl_seconds=60)
    cached = await mgr.get_cached_response(key)
    assert cached is not None
    assert cached.choices[0].message.content == "Hello!"
    assert cached.cached is True
