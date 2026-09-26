import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_completions_endpoint(client: AsyncClient):
    payload = {
        "model": "mock",
        "messages": [{"role": "user", "content": "Explain TCP in simple terms"}],
        "temperature": 0.7,
        "stream": False,
    }
    response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) > 0
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "usage" in data
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_models_endpoint(client: AsyncClient):
    response = await client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert any(m["id"] == "gemini" for m in data["data"])
    assert any(m["id"] == "openrouter" for m in data["data"])


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    resp1 = await client.get("/health")
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "healthy"

    resp2 = await client.get("/health/providers")
    assert resp2.status_code == 200

    resp3 = await client.get("/metrics")
    assert resp3.status_code == 200
    assert b"llm_requests_total" in resp3.content
