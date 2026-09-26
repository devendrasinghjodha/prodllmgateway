import asyncio
import time
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_concurrent_load_simulation():
    """
    Simulates high concurrent request load against the gateway using the mock provider.
    Demonstrates capacity and single-flight coalescing.
    """
    transport = ASGITransport(app=app)
    concurrent_requests = 50

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "model": "mock",
            "messages": [{"role": "user", "content": "Concurrent load test"}],
            "stream": False,
        }

        start = time.time()
        tasks = [client.post("/v1/chat/completions", json=payload) for _ in range(concurrent_requests)]
        responses = await asyncio.gather(*tasks)
        duration = time.time() - start

        successful = [r for r in responses if r.status_code == 200]
        assert len(successful) == concurrent_requests
        rps = concurrent_requests / duration
        print(f"\nCompleted {concurrent_requests} concurrent requests in {duration:.3f}s ({rps:.1f} RPS)")
