import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional
import redis.asyncio as redis

from app.config import settings
from app.providers.base import ChatRequest, ChatResponse

logger = logging.getLogger("prodllm.cache")

redis_client: Optional[redis.Redis] = None
_in_memory_cache: Dict[str, tuple[str, float]] = {}  # fallback: key -> (json_value, expire_at)


async def get_redis() -> Optional[redis.Redis]:
    global redis_client
    if not settings.REDIS_ENABLED:
        return None
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            await redis_client.ping()
            logger.info("Connected to Redis cache successfully.")
        except Exception as e:
            logger.warning(f"Redis connection failed ({e}). Using in-memory fallback cache.")
            redis_client = None
    return redis_client


def generate_cache_key(request: ChatRequest) -> str:
    """
    Generate deterministic SHA-256 hash representing the exact LLM request parameters.
    """
    payload_dict = {
        "model": request.model,
        "messages": [m.model_dump() for m in request.messages],
        "temperature": request.temperature,
        "top_p": request.top_p,
        "max_tokens": request.get_effective_max_tokens(),
        "stop": request.stop,
    }
    serialized = json.dumps(payload_dict, sort_keys=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"llm:cache:{digest}"


class CacheManager:
    def __init__(self, r_client: Optional[redis.Redis] = None):
        self.r = r_client

    async def get_cached_response(self, cache_key: str) -> Optional[ChatResponse]:
        """Fetch and deserialize cached ChatResponse."""
        if self.r:
            try:
                cached_json = await self.r.get(cache_key)
                if cached_json:
                    data = json.loads(cached_json)
                    response = ChatResponse.model_validate(data)
                    response.cached = True
                    return response
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # In-memory fallback
        now = time.time()
        if cache_key in _in_memory_cache:
            raw_val, expire_at = _in_memory_cache[cache_key]
            if now < expire_at:
                data = json.loads(raw_val)
                response = ChatResponse.model_validate(data)
                response.cached = True
                return response
            else:
                del _in_memory_cache[cache_key]

        return None

    async def set_cached_response(
        self,
        cache_key: str,
        response: ChatResponse,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store ChatResponse with TTL."""
        ttl = ttl_seconds or settings.CACHE_DEFAULT_TTL_SECONDS
        payload_json = response.model_dump_json()

        if self.r:
            try:
                await self.r.set(cache_key, payload_json, ex=ttl)
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # In-memory fallback
        _in_memory_cache[cache_key] = (payload_json, time.time() + ttl)

    # Idempotency Helpers (Section 32)
    async def get_idempotent_response(self, idempotency_key: str) -> Optional[ChatResponse]:
        key = f"idempotency:{idempotency_key}"
        return await self.get_cached_response(key)

    async def set_idempotent_response(
        self, idempotency_key: str, response: ChatResponse
    ) -> None:
        key = f"idempotency:{idempotency_key}"
        await self.set_cached_response(
            key, response, ttl_seconds=settings.IDEMPOTENCY_TTL_SECONDS
        )
