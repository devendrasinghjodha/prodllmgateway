import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_idempotency_key_replay(client: AsyncClient):
    payload = {
        "model": "mock",
        "messages": [{"role": "user", "content": "Generate invoice #1001"}],
    }
    headers = {"Idempotency-Key": "idemp_test_abc_123"}

    # First request
    resp1 = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Second request with same idempotency key
    resp2 = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["id"] == data2["id"]
