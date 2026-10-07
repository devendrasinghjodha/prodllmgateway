import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum

from app.config import settings

logger = logging.getLogger("prodllm.circuitbreaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when request is rejected because the circuit is OPEN."""
    def __init__(self, provider_name: str, retry_after_sec: float):
        super().__init__(f"Circuit breaker for provider '{provider_name}' is OPEN. Retry in {retry_after_sec:.1f}s.")
        self.provider_name = provider_name
        self.retry_after_sec = retry_after_sec


class CircuitBreaker:
    """
    Per-provider Circuit Breaker pattern implementation.
    Transitions:
      - CLOSED -> OPEN: when consecutive failure_count >= failure_threshold
      - OPEN -> HALF_OPEN: when recovery_time has elapsed
      - HALF_OPEN -> CLOSED: when successful probe requests >= half_open_probes
      - HALF_OPEN -> OPEN: on any failure during probe
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        recovery_time_seconds: float | None = None,
        half_open_probes: int | None = None,
        on_state_change: Callable[[str, CircuitState, CircuitState], None] | None = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold or settings.CB_FAILURE_THRESHOLD
        self.recovery_time = recovery_time_seconds or settings.CB_RECOVERY_TIME_SECONDS
        self.half_open_probes = half_open_probes or settings.CB_HALF_OPEN_PROBES
        self.on_state_change = on_state_change

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        """Check if request is allowed through the circuit."""
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.recovery_time:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

            return False

    async def record_success(self):
        """Record successful upstream execution."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_probes:
                    self._transition_to(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def record_failure(self, exc: Exception | None = None):
        """Record upstream failure."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.warning(f"Probe failed in HALF_OPEN for {self.name}. Opening circuit.")
                self._transition_to(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    logger.error(
                        f"Circuit for {self.name} tripped to OPEN after {self.failure_count} consecutive failures."
                    )
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0

        logger.info(f"CircuitBreaker[{self.name}]: {old_state.value} -> {new_state.value}")
        if self.on_state_change:
            self.on_state_change(self.name, old_state, new_state)

    def get_remaining_recovery_time(self) -> float:
        if self.state != CircuitState.OPEN:
            return 0.0
        elapsed = time.time() - self.last_state_change
        return max(0.0, self.recovery_time - elapsed)


class CircuitBreakerRegistry:
    """Registry maintaining one circuit breaker per provider."""
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get_breaker(self, name: str) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name)
        return self._breakers[name]

    def all_states(self) -> dict[str, str]:
        return {name: cb.state.value for name, cb in self._breakers.items()}


circuit_breakers = CircuitBreakerRegistry()
