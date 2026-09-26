import logging
from typing import Optional
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.auth.api_keys import hash_api_key, AuthenticatedUser
from app.database.repository import get_db_session, DatabaseRepository

logger = logging.getLogger("prodllm.auth")
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db_session),
) -> AuthenticatedUser:
    """
    Authenticate request via Bearer token.
    Validates against hash in database or static admin key.
    """
    if not settings.REQUIRE_AUTH:
        return AuthenticatedUser(
            user_id="default_user",
            api_key_id="default_key",
            prefix="pllm_dev",
            is_admin=True,
        )

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail={"error": {"type": "authentication_error", "message": "Missing Bearer token in Authorization header"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_key = credentials.credentials
    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail={"error": {"type": "authentication_error", "message": "Empty Bearer token"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check for Admin Static Key
    if settings.ADMIN_API_KEY and raw_key == settings.ADMIN_API_KEY:
        return AuthenticatedUser(
            user_id="admin",
            api_key_id="admin_key",
            prefix=raw_key[:10],
            is_admin=True,
        )

    # Hash Key & Check DB
    key_hash = hash_api_key(raw_key)
    repo = DatabaseRepository(db)
    api_key_record = await repo.get_api_key_by_hash(key_hash)

    if not api_key_record:
        logger.warning(f"Failed authentication attempt with key prefix: {raw_key[:8]}...")
        raise HTTPException(
            status_code=401,
            detail={"error": {"type": "authentication_error", "message": "Invalid or revoked API key"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        user_id=api_key_record.user_id,
        api_key_id=api_key_record.id,
        prefix=api_key_record.prefix,
        is_admin=False,
    )
