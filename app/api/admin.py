from datetime import datetime, timedelta
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update

from app.auth.api_keys import generate_api_key, hash_api_key, AuthenticatedUser
from app.auth.middleware import get_current_user
from app.database.models import User, APIKey, RequestLog, Team, Organization
from app.database.repository import get_db_session, DatabaseRepository
from app.limits.budget import budget_manager
from app.reliability.circuit_breaker import circuit_breakers, CircuitState

logger = logging.getLogger("prodllm.api.admin")
admin_router = APIRouter(prefix="/admin", tags=["Admin Operations"])


class CreateKeyRequest(BaseModel):
    user_id: str
    user_name: Optional[str] = "Developer"
    team_id: Optional[str] = None
    expires_in_days: Optional[int] = 30


class CreateKeyResponse(BaseModel):
    key_id: str
    api_key: str  # Only returned once upon creation!
    prefix: str
    user_id: str
    created_at: datetime
    expires_at: Optional[datetime]


class KeyInfo(BaseModel):
    id: str
    user_id: str
    prefix: str
    status: str
    created_at: datetime
    expires_at: Optional[datetime]


class CreateTeamRequest(BaseModel):
    id: str
    name: str
    monthly_budget_usd: float = 100.0
    budget_policy: str = "downgrade_to_free"  # downgrade_to_free, strict_block
    org_id: Optional[str] = None


class TeamInfo(BaseModel):
    id: str
    name: str
    org_id: Optional[str]
    monthly_budget_usd: float
    budget_policy: str
    current_month_spend_usd: float
    created_at: datetime


class RequestLogItem(BaseModel):
    id: str
    user_id: Optional[str]
    team_id: Optional[str]
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    status: str
    estimated_cost: float
    created_at: datetime


def require_admin(user: AuthenticatedUser = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privilege required")
    return user


@admin_router.post("/teams", response_model=TeamInfo)
async def create_team(
    req: CreateTeamRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new Team with a monthly spend budget and downgrade policy."""
    team = Team(
        id=req.id,
        name=req.name,
        monthly_budget_usd=req.monthly_budget_usd,
        budget_policy=req.budget_policy,
        org_id=req.org_id,
        created_at=datetime.utcnow(),
    )
    db.add(team)
    await db.flush()

    budget_manager.configure_team_budget(
        team_id=req.id,
        monthly_budget_usd=req.monthly_budget_usd,
        policy=req.budget_policy,
    )

    logger.info(f"Admin created team: {req.id} (Budget: ${req.monthly_budget_usd}/mo)")
    return TeamInfo(
        id=team.id,
        name=team.name,
        org_id=team.org_id,
        monthly_budget_usd=team.monthly_budget_usd,
        budget_policy=team.budget_policy,
        current_month_spend_usd=0.0,
        created_at=team.created_at,
    )


@admin_router.get("/teams", response_model=List[TeamInfo])
async def list_teams(
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """List all teams and their live monthly spend consumption."""
    stmt = select(Team).order_by(Team.name)
    result = await db.execute(stmt)
    teams = result.scalars().all()

    team_list = []
    for t in teams:
        spend = await budget_manager.get_team_spend(t.id)
        team_list.append(
            TeamInfo(
                id=t.id,
                name=t.name,
                org_id=t.org_id,
                monthly_budget_usd=t.monthly_budget_usd,
                budget_policy=t.budget_policy,
                current_month_spend_usd=spend,
                created_at=t.created_at,
            )
        )
    return team_list


@admin_router.post("/keys", response_model=CreateKeyResponse)
async def create_key(
    req: CreateKeyRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new API Key for a user and return the raw key token."""
    repo = DatabaseRepository(db)
    user = await repo.get_user(req.user_id)
    if not user:
        user = await repo.create_user(req.user_id, req.user_name or req.user_id)
        if req.team_id:
            user.team_id = req.team_id
            await db.flush()

    raw_key, key_hash, prefix = generate_api_key("pllm_")
    expires_at = datetime.utcnow() + timedelta(days=req.expires_in_days) if req.expires_in_days else None
    key_id = f"key_{raw_key[5:15]}"

    api_key = await repo.create_api_key(
        key_id=key_id,
        user_id=user.id,
        key_hash=key_hash,
        prefix=prefix,
        expires_at=expires_at,
    )

    logger.info(f"Admin created API key: {key_id} for user: {user.id}")
    return CreateKeyResponse(
        key_id=api_key.id,
        api_key=raw_key,
        prefix=api_key.prefix,
        user_id=api_key.user_id,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@admin_router.get("/keys", response_model=List[KeyInfo])
async def list_keys(
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """List all registered API keys."""
    stmt = select(APIKey).order_by(desc(APIKey.created_at))
    result = await db.execute(stmt)
    keys = result.scalars().all()
    return [
        KeyInfo(
            id=k.id,
            user_id=k.user_id,
            prefix=k.prefix,
            status=k.status,
            created_at=k.created_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]


@admin_router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke an API key immediately."""
    stmt = update(APIKey).where(APIKey.id == key_id).values(status="revoked")
    await db.execute(stmt)
    logger.info(f"Admin revoked key: {key_id}")
    return {"status": "success", "message": f"API key {key_id} revoked"}


@admin_router.get("/requests", response_model=List[RequestLogItem])
async def get_requests(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    team_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Paginated audit request logs."""
    stmt = select(RequestLog).order_by(desc(RequestLog.created_at)).offset(offset).limit(limit)
    if provider:
        stmt = stmt.where(RequestLog.provider == provider)
    if status:
        stmt = stmt.where(RequestLog.status == status)
    if team_id:
        stmt = stmt.where(RequestLog.team_id == team_id)

    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        RequestLogItem(
            id=log.id,
            user_id=log.user_id,
            team_id=log.team_id,
            provider=log.provider,
            model=log.model,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            total_tokens=log.total_tokens,
            latency_ms=log.latency_ms,
            status=log.status,
            estimated_cost=log.estimated_cost,
            created_at=log.created_at,
        )
        for log in logs
    ]


@admin_router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    provider: str,
    admin: AuthenticatedUser = Depends(require_admin),
):
    """Manually reset a circuit breaker to CLOSED state."""
    breaker = circuit_breakers.get_breaker(provider)
    breaker.state = CircuitState.CLOSED
    breaker.failure_count = 0
    logger.info(f"Admin reset circuit breaker for {provider} to CLOSED")
    return {"status": "success", "provider": provider, "new_state": breaker.state.value}
