import pytest
from app.limits.budget import BudgetManager


@pytest.mark.asyncio
async def test_budget_spend_and_graceful_downgrade():
    mgr = BudgetManager(r_client=None)
    team_id = "ai_engineering_team"

    # Configure $10.00 monthly budget with downgrade policy
    mgr.configure_team_budget(team_id, monthly_budget_usd=10.0, policy="downgrade_to_free")

    # Initial state
    allowed, need_downgrade, spend, limit = await mgr.check_budget(team_id)
    assert allowed is True
    assert need_downgrade is False
    assert limit == 10.0

    # Record spend of $8.00 -> still within budget
    await mgr.record_spend(team_id, 8.00)
    allowed, need_downgrade, spend, _ = await mgr.check_budget(team_id)
    assert allowed is True
    assert need_downgrade is False
    assert spend == 8.00

    # Record spend of $3.00 -> total $11.00 (Exceeded!)
    await mgr.record_spend(team_id, 3.00)
    allowed, need_downgrade, spend, _ = await mgr.check_budget(team_id)
    assert allowed is True
    assert need_downgrade is True  # Triggers graceful downgrade to free tier!
    assert spend == 11.00


@pytest.mark.asyncio
async def test_budget_strict_blocking():
    mgr = BudgetManager(r_client=None)
    team_id = "finance_team"

    # Configure $5.00 monthly budget with strict blocking
    mgr.configure_team_budget(team_id, monthly_budget_usd=5.0, policy="strict_block")

    await mgr.record_spend(team_id, 6.00)
    allowed, need_downgrade, spend, _ = await mgr.check_budget(team_id)
    assert allowed is False  # Blocked!
