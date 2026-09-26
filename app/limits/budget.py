import datetime
import logging
from typing import Dict, Optional, Tuple
import redis.asyncio as redis

logger = logging.getLogger("prodllm.budget")

# In-memory spend cache fallback: key -> total_spend_usd
_in_memory_team_spend: Dict[str, float] = {}
_team_budget_configs: Dict[str, Dict] = {}


class BudgetManager:
    """
    Financial Governance & Spend Budget Manager.
    Enforces monthly USD spending limits with Graceful Free-Tier Downgrade or Strict Blocking.
    """

    def __init__(self, r_client: Optional[redis.Redis] = None):
        self.r = r_client

    def _get_month_key(self, team_id: str) -> str:
        month_str = datetime.date.today().strftime("%Y-%m")
        return f"budget:team:{team_id}:{month_str}"

    def configure_team_budget(
        self,
        team_id: str,
        monthly_budget_usd: float = 50.0,
        policy: str = "downgrade_to_free",
    ):
        """Configure team budget in memory."""
        _team_budget_configs[team_id] = {
            "budget": monthly_budget_usd,
            "policy": policy,  # downgrade_to_free, strict_block
        }

    async def get_team_spend(self, team_id: str) -> float:
        key = self._get_month_key(team_id)
        if self.r:
            try:
                val = await self.r.get(key)
                return float(val) if val else 0.0
            except Exception as e:
                logger.error(f"Redis get budget spend error: {e}")
        return _in_memory_team_spend.get(key, 0.0)

    async def record_spend(self, team_id: Optional[str], cost_usd: float):
        if not team_id or cost_usd <= 0:
            return
        key = self._get_month_key(team_id)
        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.incrbyfloat(key, cost_usd)
                pipe.expire(key, 86400 * 60)  # 60 days TTL
                await pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis record spend error: {e}")

        _in_memory_team_spend[key] = _in_memory_team_spend.get(key, 0.0) + cost_usd

    async def check_budget(
        self, team_id: Optional[str]
    ) -> Tuple[bool, bool, float, float]:
        """
        Check if team is within monthly budget.
        Returns: (is_allowed, is_downgrade_needed, current_spend, monthly_budget)
        """
        if not team_id:
            return True, False, 0.0, 999999.0

        cfg = _team_budget_configs.get(
            team_id, {"budget": 100.0, "policy": "downgrade_to_free"}
        )
        monthly_limit = cfg["budget"]
        policy = cfg["policy"]

        current_spend = await self.get_team_spend(team_id)

        if current_spend < monthly_limit:
            return True, False, current_spend, monthly_limit

        # Budget exceeded!
        logger.warning(
            f"Team '{team_id}' exceeded monthly spend limit (${current_spend:.4f} >= ${monthly_limit:.2f}). Policy: {policy}"
        )
        if policy == "downgrade_to_free":
            # Allowed to proceed, but must be downgraded to free tier models!
            return True, True, current_spend, monthly_limit
        else:
            # Strict block
            return False, False, current_spend, monthly_limit


budget_manager = BudgetManager()
