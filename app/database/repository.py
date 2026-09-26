import logging
from typing import AsyncGenerator, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import select, func, desc

from app.config import settings
from app.database.models import Base, User, APIKey, RequestLog

logger = logging.getLogger("prodllm.database")

engine: Optional[AsyncEngine] = None
async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db() -> AsyncEngine:
    global engine, async_session_factory
    try:
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
        )
        async_session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully with PostgreSQL.")
        return engine
    except Exception as e:
        if settings.USE_SQLITE_FALLBACK:
            logger.warning(
                f"Failed to connect to PostgreSQL ({e}). Falling back to SQLite: {settings.FALLBACK_SQLITE_URL}"
            )
            engine = create_async_engine(
                settings.FALLBACK_SQLITE_URL,
                echo=settings.DEBUG,
            )
            async_session_factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully with SQLite fallback.")
            return engine
        raise e


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        await init_db()
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class DatabaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user_id: str, name: str) -> User:
        user = User(id=user_id, name=name, created_at=datetime.utcnow())
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[APIKey]:
        stmt = select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.status == "active"
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_api_key(
        self,
        key_id: str,
        user_id: str,
        key_hash: str,
        prefix: str,
        expires_at: Optional[datetime] = None,
    ) -> APIKey:
        api_key = APIKey(
            id=key_id,
            user_id=user_id,
            key_hash=key_hash,
            prefix=prefix,
            status="active",
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        self.session.add(api_key)
        await self.session.flush()
        return api_key

    async def log_request(
        self,
        request_id: str,
        user_id: Optional[str],
        api_key_id: Optional[str],
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: float,
        status: str = "success",
        error_type: Optional[str] = None,
        estimated_cost: float = 0.0,
        idempotency_key: Optional[str] = None,
    ) -> RequestLog:
        req_log = RequestLog(
            id=request_id,
            user_id=user_id,
            api_key_id=api_key_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=status,
            error_type=error_type,
            estimated_cost=estimated_cost,
            idempotency_key=idempotency_key,
            created_at=datetime.utcnow(),
        )
        self.session.add(req_log)
        await self.session.flush()
        return req_log

    async def get_usage_summary(self, user_id: Optional[str] = None) -> dict:
        stmt = select(
            func.count(RequestLog.id).label("total_requests"),
            func.sum(RequestLog.prompt_tokens).label("total_prompt_tokens"),
            func.sum(RequestLog.completion_tokens).label("total_completion_tokens"),
            func.sum(RequestLog.total_tokens).label("total_tokens"),
            func.sum(RequestLog.estimated_cost).label("total_cost"),
            func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
        )
        if user_id:
            stmt = stmt.where(RequestLog.user_id == user_id)
        result = await self.session.execute(stmt)
        row = result.fetchone()
        if not row:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_latency_ms": 0.0,
            }
        return {
            "total_requests": row.total_requests or 0,
            "total_prompt_tokens": row.total_prompt_tokens or 0,
            "total_completion_tokens": row.total_completion_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0.0),
            "avg_latency_ms": float(row.avg_latency_ms or 0.0),
        }
