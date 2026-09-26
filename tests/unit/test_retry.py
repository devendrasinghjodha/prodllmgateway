import httpx
import pytest
from app.reliability.retry import with_retry, is_retriable_exception


def test_retriable_status_codes():
    resp_429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
    exc_429 = httpx.HTTPStatusError("Rate limited", request=resp_429.request, response=resp_429)
    assert is_retriable_exception(exc_429, [429, 500, 502, 503, 504]) is True

    resp_401 = httpx.Response(status_code=401, request=httpx.Request("POST", "http://test"))
    exc_401 = httpx.HTTPStatusError("Unauthorized", request=resp_401.request, response=resp_401)
    assert is_retriable_exception(exc_401, [429, 500, 502, 503, 504]) is False


@pytest.mark.asyncio
async def test_retry_successful_after_transient_failure():
    calls = 0

    async def flaky_fn():
        nonlocal calls
        calls += 1
        if calls < 3:
            resp_503 = httpx.Response(status_code=503, request=httpx.Request("POST", "http://test"))
            raise httpx.HTTPStatusError("Service Unavailable", request=resp_503.request, response=resp_503)
        return "SUCCESS"

    result = await with_retry(
        flaky_fn,
        max_attempts=3,
        initial_delay=0.01,
        backoff_factor=1.5,
    )
    assert result == "SUCCESS"
    assert calls == 3
