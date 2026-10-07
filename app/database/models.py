from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(64), primary_key=True, index=True)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    monthly_budget_usd = Column(Float, default=100.0, nullable=False)
    budget_policy = Column(String(32), default="downgrade_to_free", nullable=False)  # downgrade_to_free, strict_block
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="teams")
    users = relationship("User", back_populates="team")
    requests = relationship("RequestLog", back_populates="team")


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="users")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    requests = relationship("RequestLog", back_populates="user")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256
    prefix = Column(String(16), nullable=False)  # e.g., pllm_ab12
    status = Column(String(32), default="active", nullable=False)  # active, revoked, expired
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")
    requests = relationship("RequestLog", back_populates="api_key")


class RequestLog(Base):
    __tablename__ = "requests"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    api_key_id = Column(String(64), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="success", nullable=False)  # success, error, throttled
    error_type = Column(String(128), nullable=True)
    estimated_cost = Column(Float, default=0.0, nullable=False)
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="requests")
    team = relationship("Team", back_populates="requests")
    api_key = relationship("APIKey", back_populates="requests")
