"""
Unit tests for Self-Healing and Resilience Engine (core/resilience.py).
"""
import pytest
from core.resilience import ResilienceEngine
from schemas import WeatherEvidence


def test_transient_failure_and_retry():
    """Verify that transient failures trigger bounded retries."""
    attempts = 0

    def flaky_service():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("Temporary DNS resolution drop")
        return {"status": "ok", "telemetry": 42}

    engine = ResilienceEngine(max_retries=2)
    result, source = engine.execute_with_resilience(
        tool_name="test_service",
        step_desc="Connecting to mock telemetry",
        call_fn=flaky_service,
    )

    assert result == {"status": "ok", "telemetry": 42}
    assert source == "live"
    assert attempts == 2
    assert any(e.recovery_action == "retry_backoff" for e in engine.recovery_events)


def test_cache_fallback():
    """Test that when live call repeatedly fails, validated cache is used."""
    def failing_api():
        raise TimeoutError("Remote API gateway 504")

    engine = ResilienceEngine(max_retries=1)

    def cache_fallback():
        return engine.get_validated_weather_cache("Shanghai, China")

    result, source = engine.execute_with_resilience(
        tool_name="get_weather",
        step_desc="Querying weather with fallback",
        call_fn=failing_api,
        fallback_fn=cache_fallback,
    )

    assert result is not None
    assert source == "validated_cache"
    assert isinstance(result, WeatherEvidence)
    assert result.location == "Shanghai, China"
    assert result.is_fallback is True
    assert result.cache_age_hours is not None
    assert any(e.recovery_action == "fallback_success" for e in engine.recovery_events)


def test_stale_or_invalid_cache_rejected():
    """Verify that an unknown or invalid location returns None from cache lookup."""
    engine = ResilienceEngine()
    cached = engine.get_validated_weather_cache("NonExistentCity_99")
    assert cached is None


def test_invalid_tool_output_rejected():
    """Verify that validator function triggers failure when payload is corrupted."""
    def corrupted_service():
        return {"corrupted": True, "value": -999}

    def validator(payload):
        return "valid_token" in payload

    engine = ResilienceEngine(max_retries=1)
    result, source = engine.execute_with_resilience(
        tool_name="corrupted_tool",
        step_desc="Validating payload schema",
        call_fn=corrupted_service,
        validate_fn=validator,
    )

    assert result is None
    assert source == "safe_fail"
    assert any("Validation failed" in (e.failure_reason or "") for e in engine.recovery_events)


def test_maximum_retries_enforced():
    """Verify that retries strictly respect configured bound and never infinite loop."""
    attempts = 0

    def stubbornly_dead():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Hardware failure")

    engine = ResilienceEngine(max_retries=2)
    result, source = engine.execute_with_resilience(
        tool_name="dead_service",
        step_desc="Bounded retry enforcement",
        call_fn=stubbornly_dead,
    )

    assert result is None
    assert source == "safe_fail"
    # attempt 1 + 2 retries = 3 attempts total
    assert attempts == 3
    assert any(e.recovery_action == "exhausted_retries" for e in engine.recovery_events)


def test_reproducible_weather_failure_injection():
    """Verify test failure flag triggers demonstration retry and fallback."""
    engine = ResilienceEngine(test_weather_failure_enabled=True)

    def cache_fallback():
        return engine.get_validated_weather_cache("Kaohsiung, Taiwan")

    result, source = engine.execute_with_resilience(
        tool_name="get_weather",
        step_desc="Demo test failure scenario",
        call_fn=lambda: WeatherEvidence(
            location="Kaohsiung, Taiwan",
            data_source="live_open_meteo",
            timestamp="2026-10-17T00:00:00Z",
        ),
        fallback_fn=cache_fallback,
    )

    assert result is not None
    assert source == "validated_cache"
    assert any("DEMO_INJECTED_TRANSIENT_TIMEOUT" in (e.failure_reason or "") for e in engine.recovery_events)
