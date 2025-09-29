import time

import pytest

from src.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_breaker_opens_after_failures():
    cb = CircuitBreaker(
        failure_threshold=2, recovery_timeout=0.2, expected_exception=ValueError
    )

    call_count = {"n": 0}

    @cb
    def unstable():
        call_count["n"] += 1
        raise ValueError("boom")

    # First failure - still CLOSED
    with pytest.raises(ValueError):
        unstable()
    assert cb.state == CircuitState.CLOSED

    # Second failure - should OPEN
    with pytest.raises(ValueError):
        unstable()
    assert cb.state == CircuitState.OPEN

    # While OPEN and before timeout - immediate rejection
    with pytest.raises(Exception) as exc:
        unstable()
    assert "OPEN" in str(exc.value)

    # After timeout it should move to HALF_OPEN and allow a trial call
    time.sleep(0.25)

    # Success path should close it again
    @cb
    def stable():
        return "ok"

    assert stable() == "ok"
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(
        failure_threshold=3, recovery_timeout=1.0, expected_exception=RuntimeError
    )

    failures = {"n": 0}

    @cb
    def sometimes():
        if failures["n"] < 2:
            failures["n"] += 1
            raise RuntimeError("temp")
        return 42

    # Two failures then success - should never OPEN
    with pytest.raises(RuntimeError):
        sometimes()
    with pytest.raises(RuntimeError):
        sometimes()
    assert cb.state == CircuitState.CLOSED  # Not yet at threshold
    assert sometimes() == 42
    assert cb.failure_count == 0
