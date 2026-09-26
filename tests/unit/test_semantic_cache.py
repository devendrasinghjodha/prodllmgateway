import pytest
from app.cache.semantic import SemanticCache, simple_embedding, cosine_similarity
from app.providers.base import ChatMessage, ChatResponse, ChatChoice, ChatChoiceMessage, Usage


def test_cosine_similarity_identical_and_orthogonal():
    v1 = simple_embedding("Explain quantum computing")
    v2 = simple_embedding("Explain quantum computing")
    v_diff = simple_embedding("Recipe for chocolate cake")

    sim_identical = cosine_similarity(v1, v2)
    sim_different = cosine_similarity(v1, v_diff)

    assert sim_identical >= 0.99
    assert sim_different < 0.70


@pytest.mark.asyncio
async def test_semantic_cache_hit_and_miss():
    cache = SemanticCache(similarity_threshold=0.80)
    messages_initial = [ChatMessage(role="user", content="How do I configure nginx reverse proxy?")]
    dummy_resp = ChatResponse(
        id="chatcmpl-sem-123",
        model="gemini",
        choices=[ChatChoice(index=0, message=ChatChoiceMessage(role="assistant", content="Nginx configuration guide..."))],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )

    await cache.store(messages_initial, "gemini", dummy_resp)

    # Similar query (Semantic HIT)
    messages_similar = [ChatMessage(role="user", content="How do I configure nginx reverse proxy server?")]
    match = await cache.search(messages_similar, "gemini")
    assert match is not None
    resp, score = match
    assert score >= 0.80
    assert resp.cached is True
    assert "Nginx configuration guide" in resp.choices[0].message.content

    # Unrelated query (Semantic MISS)
    messages_unrelated = [ChatMessage(role="user", content="What is the capital of France?")]
    miss = await cache.search(messages_unrelated, "gemini")
    assert miss is None
