import pytest
from app.limits.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter():
    limiter = RateLimiter(r_client=None)
    key = "test_user_key"

    # Limit of 3 requests per 60s
    allowed1, _, _ = await limiter.check_sliding_window(key, max_requests=3, window_seconds=60)
    allowed2, _, _ = await limiter.check_sliding_window(key, max_requests=3, window_seconds=60)
    allowed3, _, _ = await limiter.check_sliding_window(key, max_requests=3, window_seconds=60)
    allowed4, _, _ = await limiter.check_sliding_window(key, max_requests=3, window_seconds=60)

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is True
    assert allowed4 is False
