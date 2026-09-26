import pytest
from app.providers.mock import MockProvider
from app.providers.base import ChatRequest, ChatMessage


@pytest.mark.asyncio
async def test_mock_provider_chat():
    provider = MockProvider(simulated_latency_ms=2.0)
    req = ChatRequest(
        model="mock",
        messages=[ChatMessage(role="user", content="Hello test")],
    )
    resp = await provider.chat(req)
    assert resp.choices[0].message.role == "assistant"
    assert "Mock response" in resp.choices[0].message.content
    assert resp.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_stream():
    provider = MockProvider(simulated_latency_ms=1.0)
    req = ChatRequest(
        model="mock",
        messages=[ChatMessage(role="user", content="Hello stream")],
        stream=True,
    )
    chunks = []
    async for chunk in provider.stream(req):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert chunks[-1].choices[0].finish_reason == "stop"
