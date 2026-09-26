import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_embeddings_endpoint(client: AsyncClient):
    payload = {
        "input": ["Explain TCP", "Explain UDP"],
        "model": "text-embedding-3-small",
    }
    res = await client.post("/v1/embeddings", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 2
    assert len(data["data"][0]["embedding"]) > 0


@pytest.mark.asyncio
async def test_images_generations_endpoint(client: AsyncClient):
    payload = {
        "prompt": "A futuristic server room with glowing fiber optic cables",
        "n": 1,
        "size": "1024x1024",
    }
    res = await client.post("/v1/images/generations", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["data"]) == 1
    assert "url" in data["data"][0]


@pytest.mark.asyncio
async def test_audio_transcriptions_endpoint(client: AsyncClient):
    files = {"file": ("audio_sample.wav", b"RIFF....WAVEfmt...", "audio/wav")}
    res = await client.post("/v1/audio/transcriptions", files=files, data={"model": "whisper-1"})
    assert res.status_code == 200
    data = res.json()
    assert "text" in data


@pytest.mark.asyncio
async def test_dashboard_endpoint(client: AsyncClient):
    res = await client.get("/dashboard")
    assert res.status_code == 200
    assert "ProdLLM Gateway" in res.text
    assert "Active Providers" in res.text
