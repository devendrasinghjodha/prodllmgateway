import asyncio
import logging
import time
from typing import Callable, Awaitable, Dict, Optional
import redis.asyncio as redis

from app.config import settings
from app.providers.base import ChatResponse
from app.cache.redis import CacheManager

logger = logging.getLogger("prodllm.singleflight")

# Local in-memory single-flight tracker
_local_flights: Dict[str, asyncio.Event] = {}
_local_results: Dict[str, ChatResponse] = {}
_flight_lock = asyncio.Lock()


class SingleFlight:
    """
    Request coalescer to prevent duplicate simultaneous upstream LLM calls.
    Uses distributed Redis SETNX locks or in-memory asyncio Events.
    """

    def __init__(self, cache_manager: CacheManager, r_client: Optional[redis.Redis] = None):
        self.cache_manager = cache_manager
        self.r = r_client

    async def execute(
        self,
        cache_key: str,
        fn: Callable[[], Awaitable[ChatResponse]],
    ) -> tuple[ChatResponse, bool]:
        """
        Execute the function if this is the leader request, or wait for the leader's result.
        Returns: (ChatResponse, is_coalesced)
        """
        lock_key = f"lock:{cache_key}"
        lock_ttl_ms = settings.SINGLEFLIGHT_LOCK_TTL_MS

        # 1. Distributed Single-Flight with Redis
        if self.r:
            try:
                # Try acquiring lock
                acquired = await self.r.set(lock_key, "locked", nx=True, px=lock_ttl_ms)
                if acquired:
                    # We are the leader request
                    try:
                        result = await fn()
                        # Cache the response for followers
                        await self.cache_manager.set_cached_response(cache_key, result)
                        return result, False
                    finally:
                        await self.r.delete(lock_key)
                else:
                    # We are a follower request -> wait for leader to fill cache
                    poll_interval = 0.05  # 50ms
                    max_wait_time = lock_ttl_ms / 1000.0
                    start_time = time.time()

                    while time.time() - start_time < max_wait_time:
                        await asyncio.sleep(poll_interval)
                        cached = await self.cache_manager.get_cached_response(cache_key)
                        if cached:
                            logger.info(f"Request coalesced successfully for key {cache_key[:16]}...")
                            return cached, True

                    # Timeout waiting for leader -> fallback to direct call
                    logger.warning(f"Single-flight wait timed out for {cache_key[:16]}..., executing directly.")
                    return await fn(), False
            except Exception as e:
                logger.error(f"Redis single-flight error: {e}")

        # 2. Local In-Memory Single-Flight
        async with _flight_lock:
            if cache_key in _local_flights:
                event = _local_flights[cache_key]
                is_leader = False
            else:
                event = asyncio.Event()
                _local_flights[cache_key] = event
                is_leader = True

        if is_leader:
            try:
                result = await fn()
                _local_results[cache_key] = result
                await self.cache_manager.set_cached_response(cache_key, result)
                return result, False
            finally:
                event.set()
                async with _flight_lock:
                    _local_flights.pop(cache_key, None)
                    # keep result briefly
                    asyncio.create_task(self._cleanup_local_result(cache_key))
        else:
            # Follower wait
            try:
                await asyncio.wait_for(event.wait(), timeout=15.0)
                if cache_key in _local_results:
                    return _local_results[cache_key], True
                cached = await self.cache_manager.get_cached_response(cache_key)
                if cached:
                    return cached, True
            except asyncio.TimeoutError:
                pass
            return await fn(), False

    async def _cleanup_local_result(self, key: str):
        await asyncio.sleep(2.0)
        _local_results.pop(key, None)
