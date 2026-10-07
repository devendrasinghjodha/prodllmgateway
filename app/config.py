from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Settings
    APP_NAME: str = "ProdLLM Gateway"
    APP_ENV: str = "production"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Authentication & Security
    API_KEY_HEADER: str = "Authorization"
    API_KEY_PREFIX: str = "pllm_"
    REQUIRE_AUTH: bool = True
    ADMIN_API_KEY: str = "pllm_admin_secret_key_prodllm"

    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prodllm"
    FALLBACK_SQLITE_URL: str = "sqlite+aiosqlite:///./prodllm.db"
    USE_SQLITE_FALLBACK: bool = True
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Redis Cache & Fast State
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_DEFAULT_TTL_SECONDS: int = 3600  # 1 hour
    IDEMPOTENCY_TTL_SECONDS: int = 86400  # 24 hours
    SINGLEFLIGHT_LOCK_TTL_MS: int = 15000  # 15 seconds

    # Rate Limiting & Quotas
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    DEFAULT_DAILY_TOKEN_QUOTA: int = 500000

    # Concurrency & Backpressure
    MAX_CONCURRENT_REQUESTS: int = 1000
    PRIORITY_QUEUE_CAPACITY: int = 2000

    # Model Provider Credentials & Endpoints
    GEMINI_API_KEY: str | None = None
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_DEFAULT_MODEL: str = "gemini-1.5-flash"

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "meta-llama/llama-3.2-3b-instruct:free"

    AGNES_API_KEY: str | None = None
    AGNES_BASE_URL: str = "https://api.agnes.ai/v1"
    AGNES_DEFAULT_MODEL: str = "agnes-standard"

    # Reliability Settings
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_INITIAL_DELAY_SECONDS: float = 0.2
    RETRY_BACKOFF_FACTOR: float = 2.0
    RETRY_STATUS_CODES: list[int] = [429, 500, 502, 503, 504]

    # Circuit Breaker Settings
    CB_FAILURE_THRESHOLD: int = 5
    CB_RECOVERY_TIME_SECONDS: float = 30.0
    CB_HALF_OPEN_PROBES: int = 2

    # Request Hedging Settings
    HEDGING_ENABLED: bool = False
    HEDGING_DELAY_MS: int = 800

    # Health Checks
    HEALTH_CHECK_INTERVAL_SECONDS: int = 30

    # Observability
    PROMETHEUS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "prodllm-gateway"

    # Routing Defaults
    ROUTING_STRATEGY: str = "auto"  # auto, latency, cost, priority, ab_test, canary
    CANARY_TARGET_MODEL: str = "openrouter"
    CANARY_WEIGHT: float = 0.1  # 10% traffic to canary


settings = Settings()
