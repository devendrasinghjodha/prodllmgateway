import datetime
import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger("prodllm.quota")

# In-memory quota fallback: key -> tokens_used
_in_memory_quota: dict[str, int] = {}


class QuotaManager:
    """
    Manages per-user daily token quotas using Redis counters.
    Keys formatted as: quota:user:{user_id}:{YYYY-MM-DD}
    """

    def __init__(self, r_client: redis.Redis | None = None):
        self.r = r_client

    def _get_today_key(self, user_id: str) -> str:
        today_str = datetime.date.today().isoformat()
        return f"quota:user:{user_id}:{today_str}"

    async def get_used_tokens(self, user_id: str) -> int:
        key = self._get_today_key(user_id)
        if self.r:
            try:
                val = await self.r.get(key)
                return int(val) if val else 0
            except Exception as e:
                logger.error(f"Redis get quota error: {e}")
        return _in_memory_quota.get(key, 0)

    async def consume_tokens(self, user_id: str, tokens: int) -> int:
        if tokens <= 0:
            return await self.get_used_tokens(user_id)
        key = self._get_today_key(user_id)
        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.incrby(key, tokens)
                pipe.expire(key, 86400 * 2)  # 2 days TTL
                results = await pipe.execute()
                return results[0]
            except Exception as e:
                logger.error(f"Redis consume quota error: {e}")

        _in_memory_quota[key] = _in_memory_quota.get(key, 0) + tokens
        return _in_memory_quota[key]

    async def check_quota(
        self, user_id: str, max_daily_tokens: int | None = None
    ) -> tuple[bool, int, int]:
        """
        Check if user is within their daily token limit.
        Returns: (is_allowed, used_tokens, remaining_tokens)
        """
        limit = max_daily_tokens or settings.DEFAULT_DAILY_TOKEN_QUOTA
        used = await self.get_used_tokens(user_id)
        allowed = used < limit
        remaining = max(0, limit - used)
        return allowed, used, remaining
