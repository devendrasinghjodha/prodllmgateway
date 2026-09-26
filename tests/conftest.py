import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test environment
os.environ["APP_ENV"] = "test"
os.environ["REQUIRE_AUTH"] = "false"
os.environ["REDIS_ENABLED"] = "false"
os.environ["USE_SQLITE_FALLBACK"] = "true"
os.environ["FALLBACK_SQLITE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.main import app
from app.config import settings
from app.database.repository import init_db
from app.routing.router import router
from app.providers.mock import MockProvider


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    await init_db()
    # Register fast mock provider for testing
    router.register_provider(MockProvider(simulated_latency_ms=1.0))


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
