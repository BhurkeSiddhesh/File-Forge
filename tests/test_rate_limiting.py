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


# ---------------------------------------------------------------------------
# Client identity (issue #11)
#
# The limiter bucketed on request.client.host. Behind Cloudflare -> nginx ->
# uvicorn that value is derived from X-Forwarded-For, which nginx *appends* to
# whatever the client sent and uvicorn trusts by default — so rotating a
# fabricated XFF gave an attacker a fresh bucket per request.
# ---------------------------------------------------------------------------

class TestClientIdentity:
    def test_cf_connecting_ip_wins_over_forwarded_for(self):
        from main import client_identity

        class _Req:
            headers = {
                "cf-connecting-ip": "203.0.113.7",
                "x-forwarded-for": "10.0.0.1",
                "x-real-ip": "10.0.0.2",
            }
            client = None

        assert client_identity(_Req()) == "203.0.113.7"

    def test_falls_back_to_x_real_ip_then_peer(self):
        from main import client_identity

        class _WithReal:
            headers = {"x-real-ip": "198.51.100.4", "x-forwarded-for": "10.0.0.1"}
            client = None

        class _Peer:
            headers = {"x-forwarded-for": "10.0.0.1"}

            class client:
                host = "192.0.2.9"

        assert client_identity(_WithReal()) == "198.51.100.4"
        assert client_identity(_Peer()) == "192.0.2.9"

    def test_spoofed_forwarded_for_does_not_reset_the_bucket(self, rate_limited_client):
        """The attack from the issue: rotate XFF, keep the real CF header."""
        codes = []
        for i in range(6):
            resp = rate_limited_client.post(
                "/api/pdf/convert-to-word",
                headers={
                    "CF-Connecting-IP": "203.0.113.10",
                    "X-Forwarded-For": f"10.0.0.{i}",   # a different lie each time
                },
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
            codes.append(resp.status_code)

        # heavy limit is 2 in this fixture: the first two get through (whatever
        # the handler makes of the payload), the rest are refused.
        assert codes.count(429) == 4, codes
        assert 429 not in codes[:2], codes

    def test_distinct_cf_ips_get_distinct_buckets(self, rate_limited_client):
        first = rate_limited_client.post(
            "/api/pdf/convert-to-word",
            headers={"CF-Connecting-IP": "203.0.113.20"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
        for _ in range(3):
            rate_limited_client.post(
                "/api/pdf/convert-to-word",
                headers={"CF-Connecting-IP": "203.0.113.20"},
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
        blocked = rate_limited_client.post(
            "/api/pdf/convert-to-word",
            headers={"CF-Connecting-IP": "203.0.113.20"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
        other = rate_limited_client.post(
            "/api/pdf/convert-to-word",
            headers={"CF-Connecting-IP": "203.0.113.21"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert first.status_code != 429
        assert blocked.status_code == 429
        assert other.status_code != 429, "a different real IP must have its own bucket"


class TestLimiterStateIsBounded:
    """defaultdict(deque) grew one entry per key seen since boot, forever."""

    def test_prune_drops_drained_keys(self):
        limiter = SlidingWindowRateLimiter(window_seconds=0.05)
        for i in range(200):
            limiter.check(f"ip{i}:light", 5)
        assert len(limiter._hits) == 200

        import time as _time
        _time.sleep(0.06)
        removed = limiter.prune()

        assert removed == 200
        assert len(limiter._hits) == 0

    def test_prune_keeps_live_keys(self):
        limiter = SlidingWindowRateLimiter(window_seconds=60)
        limiter.check("live:light", 5)
        assert limiter.prune() == 0
        assert "live:light" in limiter._hits

    def test_emptied_bucket_is_reclaimed(self):
        """The specific leak: check() pops expired hits but left the empty deque."""
        limiter = SlidingWindowRateLimiter(window_seconds=0.05)
        limiter.check("transient:light", 5)

        import time as _time
        _time.sleep(0.06)
        limiter.check("transient:light", 5)   # drains the deque, re-adds one hit
        _time.sleep(0.06)

        assert limiter.prune() == 1
        assert limiter._hits == {}


class TestMultiWorkerGuard:
    def test_boot_refuses_multiple_workers(self, monkeypatch):
        from main import _assert_single_worker

        monkeypatch.setenv("WEB_CONCURRENCY", "4")
        monkeypatch.delenv("ALLOW_MULTI_WORKER", raising=False)
        with pytest.raises(RuntimeError, match="single worker"):
            _assert_single_worker()

    def test_single_worker_and_explicit_opt_out_are_fine(self, monkeypatch):
        from main import _assert_single_worker

        monkeypatch.setenv("WEB_CONCURRENCY", "1")
        _assert_single_worker()

        monkeypatch.setenv("WEB_CONCURRENCY", "4")
        monkeypatch.setenv("ALLOW_MULTI_WORKER", "1")
        _assert_single_worker()
