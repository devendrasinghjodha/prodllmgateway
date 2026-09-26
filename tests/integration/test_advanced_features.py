import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_prompts_lifecycle_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer pllm_admin_secret_key_prodllm"}

        # 1. Create Prompt
        create_res = await client.post(
            "/v1/prompts",
            headers=headers,
            json={
                "name": "integration_greeting",
                "template": "Hello {name}, welcome to {service}!",
                "description": "Integration test greeting",
            },
        )
        assert create_res.status_code == 200
        p_data = create_res.json()
        assert p_data["name"] == "integration_greeting"
        assert p_data["version"] == 1

        # 2. Render Prompt
        render_res = await client.post(
            "/v1/prompts/integration_greeting/render",
            headers=headers,
            json={"variables": {"name": "Charlie", "service": "ProdLLM"}},
        )
        assert render_res.status_code == 200
        assert render_res.json()["rendered"] == "Hello Charlie, welcome to ProdLLM!"


@pytest.mark.asyncio
async def test_feedback_and_evals_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer pllm_admin_secret_key_prodllm"}

        # 1. Submit Feedback
        fb_res = await client.post(
            "/v1/feedback",
            headers=headers,
            json={
                "model": "gemini",
                "rating": 5,
                "thumb": "up",
                "comment": "Super fast and accurate response!",
            },
        )
        assert fb_res.status_code == 200
        assert fb_res.json()["rating"] == 5

        # 2. Check Stats
        stats_res = await client.get("/v1/feedback/stats", headers=headers)
        assert stats_res.status_code == 200
        assert stats_res.json()["total_submissions"] >= 1

        # 3. Test Heuristic Evals Endpoint
        eval_res = await client.post(
            "/v1/evals/test",
            headers=headers,
            json={
                "text": "```json\n{\"status\": \"ok\", \"result\": 42}\n```",
                "expect_json": True,
                "required_json_keys": ["status", "result"],
            },
        )
        assert eval_res.status_code == 200
        assert eval_res.json()["passed"] is True


@pytest.mark.asyncio
async def test_batches_and_dlq_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer pllm_admin_secret_key_prodllm"}

        # 1. Create Batch Job
        batch_res = await client.post(
            "/v1/batches",
            headers=headers,
            json={
                "requests": [
                    {
                        "custom_id": "req-1",
                        "body": {
                            "model": "mock",
                            "messages": [{"role": "user", "content": "Ping"}],
                        },
                    }
                ]
            },
        )
        assert batch_res.status_code == 200
        batch_id = batch_res.json()["id"]

        # 2. Get Batch Status
        get_batch_res = await client.get(f"/v1/batches/{batch_id}", headers=headers)
        assert get_batch_res.status_code == 200
        assert get_batch_res.json()["id"] == batch_id

        # 3. Check DLQ list
        dlq_res = await client.get("/v1/dlq", headers=headers)
        assert dlq_res.status_code == 200
        assert isinstance(dlq_res.json(), list)
