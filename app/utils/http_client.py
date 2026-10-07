import logging

import httpx

logger = logging.getLogger("prodllm.http")

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """
    Returns a shared, connection-pooled AsyncClient configured for high-concurrency throughput.
    Avoids TCP socket exhaustion under 10k RPS load.
    """
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(
            max_keepalive_connections=200,
            max_connections=2000,
            keepalive_expiry=30.0,
        )
        timeout = httpx.Timeout(
            timeout=30.0,
            connect=5.0,
            read=25.0,
            write=10.0,
        )
        _client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            http2=True,
        )
        logger.info("Initialized high-concurrency shared HTTP client pool (max_connections=2000).")
    return _client


async def close_http_client():
    """Gracefully closes all pooled connections on server shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed shared HTTP client pool.")
