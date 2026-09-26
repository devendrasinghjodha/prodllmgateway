import json
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_streaming_chat_completions(client: AsyncClient):
    payload = {
        "model": "mock",
        "messages": [{"role": "user", "content": "Stream test"}],
        "stream": True,
    }

    async with client.stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        chunks = []
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                if data_str:
                    chunks.append(json.loads(data_str))

        assert len(chunks) > 0
        assert chunks[0]["object"] == "chat.completion.chunk"
