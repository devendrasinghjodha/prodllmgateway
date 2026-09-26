import asyncio
import pytest
from app.reliability.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_breaker_transitions():
    cb = CircuitBreaker(
        name="test-provider",
        failure_threshold=3,
        recovery_time_seconds=0.2,
        half_open_probes=2,
    )

    # Initial state CLOSED
    assert cb.state == CircuitState.CLOSED
    assert await cb.can_execute() is True

    # Record 2 failures -> still CLOSED
    await cb.record_failure(Exception("Fail 1"))
    await cb.record_failure(Exception("Fail 2"))
    assert cb.state == CircuitState.CLOSED

    # 3rd failure -> trips to OPEN
    await cb.record_failure(Exception("Fail 3"))
    assert cb.state == CircuitState.OPEN
    assert await cb.can_execute() is False

    # Wait for recovery cooldown
    await asyncio.sleep(0.25)

    # Cooldown passed -> transitions to HALF_OPEN on next check
    assert await cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # 1st probe success -> still HALF_OPEN
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    # 2nd probe success -> back to CLOSED
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert await cb.can_execute() is True
