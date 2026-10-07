import hashlib
import secrets

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    user_id: str
    api_key_id: str
    prefix: str
    is_admin: bool = False
    team_id: str | None = None
    org_id: str | None = None


APIKey = AuthenticatedUser


def hash_api_key(api_key: str) -> str:
    """Compute SHA-256 hash of API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "pllm_") -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (raw_key, key_hash, prefix)
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_part}"
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:10]
    return raw_key, key_hash, key_prefix
