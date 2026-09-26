import asyncio
import logging
import random
from typing import Callable, Awaitable, List, Optional, TypeVar
import httpx

from app.config import settings

logger = logging.getLogger("prodllm.retry")
T = TypeVar("T")


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


def is_retriable_exception(exc: Exception, status_codes: List[int]) -> bool:
    """
    Determine if an exception or HTTP status code is transient/retriable.
    Retries: 429, 500, 502, 503, 504, timeouts, connection drops.
    Does NOT retry: 400, 401, 403, 404, or validation errors.
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in status_codes

    return False


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    max_attempts: Optional[int] = None,
    initial_delay: Optional[float] = None,
    backoff_factor: Optional[float] = None,
    retriable_status_codes: Optional[List[int]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> T:
    """
    Execute async function with exponential backoff and full jitter.
    """
    attempts = max_attempts or settings.RETRY_MAX_ATTEMPTS
    delay = initial_delay or settings.RETRY_INITIAL_DELAY_SECONDS
    factor = backoff_factor or settings.RETRY_BACKOFF_FACTOR
    status_codes = retriable_status_codes or settings.RETRY_STATUS_CODES

    last_exception: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exception = exc
            if attempt == attempts or not is_retriable_exception(exc, status_codes):
                raise exc

            # Calculate exponential backoff with full jitter
            jitter = random.uniform(0.5, 1.5)
            sleep_duration = (delay * (factor ** (attempt - 1))) * jitter

            logger.warning(
                f"Attempt {attempt}/{attempts} failed ({exc}). Retrying in {sleep_duration:.3f}s..."
            )
            if on_retry:
                on_retry(attempt, exc, sleep_duration)

            await asyncio.sleep(sleep_duration)

    if last_exception:
        raise last_exception
    raise RetryError("Retry loop ended without result or exception.")
