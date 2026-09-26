import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_key_lifecycle(client: AsyncClient):
    # 1. Create Key
    create_payload = {
        "user_id": "test_user_99",
        "user_name": "Test User",
        "expires_in_days": 10,
    }
    resp = await client.post("/admin/keys", json=create_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"].startswith("pllm_")
    key_id = data["key_id"]

    # 2. List Keys
    list_resp = await client.get("/admin/keys")
    assert list_resp.status_code == 200
    keys = list_resp.json()
    assert any(k["id"] == key_id for k in keys)

    # 3. Revoke Key
    revoke_resp = await client.delete(f"/admin/keys/{key_id}")
    assert revoke_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_circuit_breaker_reset(client: AsyncClient):
    resp = await client.post("/admin/circuit-breaker/reset", params={"provider": "gemini"})
    assert resp.status_code == 200
    assert resp.json()["new_state"] == "CLOSED"
