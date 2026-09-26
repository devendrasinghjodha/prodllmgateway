import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_team_and_budget_lifecycle(client: AsyncClient):
    # 1. Create Team with Budget
    team_payload = {
        "id": "ml_research_team",
        "name": "ML Research Team",
        "monthly_budget_usd": 75.0,
        "budget_policy": "downgrade_to_free",
    }
    create_res = await client.post("/admin/teams", json=team_payload)
    assert create_res.status_code == 200
    team_data = create_res.json()
    assert team_data["id"] == "ml_research_team"
    assert team_data["monthly_budget_usd"] == 75.0

    # 2. List Teams
    list_res = await client.get("/admin/teams")
    assert list_res.status_code == 200
    teams = list_res.json()
    assert any(t["id"] == "ml_research_team" for t in teams)
