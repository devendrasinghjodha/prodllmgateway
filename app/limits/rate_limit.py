import logging
import time
from typing import Dict, List, Optional
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger("prodllm.ratelimit")

# In-memory sliding window fallback: key -> list of timestamps
_in_memory_ratelimit: Dict[str, List[float]] = {}


class RateLimiter:
    """
    Multi-algorithm Rate Limiter supporting:
    1. Sliding Window with Redis Sorted Sets (ZADD / ZREMRANGEBYSCORE / ZCARD)
    2. Fixed Window with Redis INCR + EXPIRE
    3. In-Memory Sliding Window fallback
    """

    def __init__(self, r_client: Optional[redis.Redis] = None):
        self.r = r_client

    async def check_sliding_window(
        self,
        identifier: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Sliding Window Rate Limiter.
        Returns: (is_allowed, current_count, remaining_limit)
        """
        now = time.time()
        window_start = now - window_seconds
        key = f"ratelimit:sliding:{identifier}"

        if self.r:
            try:
                pipe = self.r.pipeline()
                # 1. Remove timestamps outside the sliding window
                pipe.zremrangebyscore(key, 0, window_start)
                # 2. Add current request timestamp
                pipe.zadd(key, {str(now): now})
                # 3. Count total elements in the window
                pipe.zcard(key)
                # 4. Set TTL on the sorted set
                pipe.expire(key, window_seconds + 5)
                results = await pipe.execute()

                current_count = results[2]
                allowed = current_count <= max_requests
                remaining = max(0, max_requests - current_count)

                return allowed, current_count, remaining
            except Exception as e:
                logger.error(f"Redis sliding window rate limit error: {e}")

        # In-Memory Sliding Window Fallback
        timestamps = _in_memory_ratelimit.get(identifier, [])
        # Prune old timestamps
        timestamps = [ts for ts in timestamps if ts > window_start]
        timestamps.append(now)
        _in_memory_ratelimit[identifier] = timestamps

        current_count = len(timestamps)
        allowed = current_count <= max_requests
        remaining = max(0, max_requests - current_count)

        return allowed, current_count, remaining

    async def check_fixed_window(
        self,
        identifier: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Fixed Window Counter with Redis INCR.
        """
        current_window = int(time.time() / window_seconds)
        key = f"ratelimit:fixed:{identifier}:{current_window}"

        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds * 2)
                results = await pipe.execute()
                count = results[0]
                allowed = count <= max_requests
                remaining = max(0, max_requests - count)
                return allowed, count, remaining
            except Exception as e:
                logger.error(f"Redis fixed window rate limit error: {e}")

        # Fallback to sliding window in-memory
        return await self.check_sliding_window(identifier, max_requests, window_seconds)

    async def is_rate_limited(
        self,
        identifier: str,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> bool:
        max_req = max_requests or settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        win_sec = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        allowed, _, _ = await self.check_sliding_window(identifier, max_req, win_sec)
        return not allowed
