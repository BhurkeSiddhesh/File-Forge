"""Tests for per-IP rate limiting (Issue #47)."""
import pytest
from fastapi.testclient import TestClient

from main import app, SlidingWindowRateLimiter, RATE_LIMIT_HEAVY_PATHS


@pytest.fixture
def rate_limited_client():
    """Client with rate limiting enabled and low limits."""
    previous = (
        app.state.rate_limit_enabled,
        app.state.rate_limit_heavy,
        app.state.rate_limit_light,
    )
    app.state.rate_limit_enabled = True
    app.state.rate_limit_heavy = 2
    app.state.rate_limit_light = 4
    app.state.rate_limiter.reset()

    client = TestClient(app)
    yield client

    (
        app.state.rate_limit_enabled,
        app.state.rate_limit_heavy,
        app.state.rate_limit_light,
    ) = previous
    app.state.rate_limiter.reset()


class TestSlidingWindowRateLimiter:
    def test_allows_up_to_limit(self):
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        for _ in range(5):
            allowed, _ = limiter.check("ip1:light", 5)
            assert allowed

    def test_blocks_over_limit_with_retry_after(self):
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        for _ in range(3):
            limiter.check("ip1:light", 3)
        allowed, retry_after = limiter.check("ip1:light", 3)
        assert not allowed
        assert 0 < retry_after <= 61

    def test_keys_are_independent(self):
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        for _ in range(3):
            limiter.check("ip1:light", 3)
        allowed, _ = limiter.check("ip2:light", 3)
        assert allowed

    def test_reset_clears_state(self):
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        for _ in range(3):
            limiter.check("ip1:light", 3)
        limiter.reset()
        allowed, _ = limiter.check("ip1:light", 3)
        assert allowed


class TestRateLimitMiddleware:
    def test_light_endpoint_returns_429_over_limit(self, rate_limited_client):
        # Limit is 4/min for light endpoints; the 5th request must be rejected.
        responses = [
            rate_limited_client.post("/api/pdf/remove-password", files={}, data={})
            for _ in range(5)
        ]
        assert responses[-1].status_code == 429
        assert "Retry-After" in responses[-1].headers
        assert "Too many requests" in responses[-1].json()["detail"]

    def test_heavy_endpoint_has_stricter_limit(self, rate_limited_client):
        # Heavy limit is 2/min; the 3rd request must be rejected even though
        # the light limit (4/min) has not been reached.
        responses = [
            rate_limited_client.post("/api/pdf/convert-to-word", files={}, data={})
            for _ in range(3)
        ]
        assert responses[-1].status_code == 429

    def test_non_api_paths_not_limited(self, rate_limited_client):
        for _ in range(10):
            resp = rate_limited_client.get("/")
            assert resp.status_code != 429

    def test_disabled_limiter_allows_all(self, auth_client):
        # conftest disables rate limiting by default for the plain auth_client
        for _ in range(30):
            resp = auth_client.post("/api/pdf/remove-password", files={}, data={})
            assert resp.status_code != 429

    def test_heavy_paths_registered(self):
        assert "/api/pdf/convert-to-word" in RATE_LIMIT_HEAVY_PATHS
        assert "/api/workflow/execute" in RATE_LIMIT_HEAVY_PATHS
        assert "/api/pdf/convert-to-word-stream" in RATE_LIMIT_HEAVY_PATHS
