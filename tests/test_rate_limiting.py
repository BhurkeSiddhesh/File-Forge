"""Tests for per-IP rate limiting (Issue #47)."""
import pytest
from fastapi.testclient import TestClient

from main import (
    app,
    SlidingWindowRateLimiter,
    RedisSlidingWindowRateLimiter,
    RATE_LIMIT_HEAVY_PATHS,
    build_rate_limiter,
)


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
    def test_cf_connecting_ip_wins_over_forwarded_for(self, monkeypatch):
        from main import client_identity
        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")

        class _Req:
            headers = {
                "cf-connecting-ip": "203.0.113.7",
                "x-forwarded-for": "10.0.0.1",
                "x-real-ip": "10.0.0.2",
                "x-ff-edge-auth": "s3cret",
            }
            client = None

        assert client_identity(_Req()) == "203.0.113.7"

    def test_falls_back_to_x_real_ip_then_peer(self, monkeypatch):
        from main import client_identity
        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")

        class _WithReal:
            headers = {"x-real-ip": "198.51.100.4", "x-forwarded-for": "10.0.0.1", "x-ff-edge-auth": "s3cret"}
            client = None

        class _Peer:
            headers = {"x-forwarded-for": "10.0.0.1", "x-ff-edge-auth": "s3cret"}

            class client:
                host = "192.0.2.9"

        assert client_identity(_WithReal()) == "198.51.100.4"
        assert client_identity(_Peer()) == "192.0.2.9"

    def test_spoofed_forwarded_for_does_not_reset_the_bucket(self, rate_limited_client, monkeypatch):
        """The attack from the issue: rotate XFF, keep the real CF header."""
        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        codes = []
        for i in range(6):
            resp = rate_limited_client.post(
                "/api/pdf/convert-to-word",
                headers={
                    "CF-Connecting-IP": "203.0.113.10",
                    "X-Forwarded-For": f"10.0.0.{i}",   # a different lie each time
                    "x-ff-edge-auth": "s3cret",
                },
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
            codes.append(resp.status_code)

        # heavy limit is 2 in this fixture: the first two get through (whatever
        # the handler makes of the payload), the rest are refused.
        assert codes.count(429) == 4, codes
        assert 429 not in codes[:2], codes

    def test_distinct_cf_ips_get_distinct_buckets(self, rate_limited_client, monkeypatch):
        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        first = rate_limited_client.post(
            "/api/pdf/convert-to-word",
            headers={"CF-Connecting-IP": "203.0.113.20", "x-ff-edge-auth": "s3cret"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
        for _ in range(3):
            rate_limited_client.post(
                "/api/pdf/convert-to-word",
                headers={"CF-Connecting-IP": "203.0.113.20", "x-ff-edge-auth": "s3cret"},
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
        blocked = rate_limited_client.post(
            "/api/pdf/convert-to-word",
            headers={"CF-Connecting-IP": "203.0.113.20", "x-ff-edge-auth": "s3cret"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
        other = rate_limited_client.post(
            "/api/pdf/convert-to-word",
            headers={"CF-Connecting-IP": "203.0.113.21", "x-ff-edge-auth": "s3cret"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert first.status_code != 429
        assert blocked.status_code == 429
        assert other.status_code != 429, "a different real IP must have its own bucket"


# ---------------------------------------------------------------------------
# Trusting the edge (issue #73)
#
# #11 stopped trusting X-Forwarded-For and moved to CF-Connecting-IP, which
# Cloudflare overwrites — but only for requests that go through Cloudflare. The
# origin answers on 443 from anywhere, so a request sent straight to it carries
# whatever CF-Connecting-IP its sender chose, and rotating it is the same bypass
# one header over. The app now honours the header only with proof the request
# came through our edge.
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, headers, peer="192.0.2.9"):
        self.headers = headers
        self.client = type("c", (), {"host": peer})() if peer else None


class TestEdgeAuthentication:
    def test_unauthenticated_edge_header_is_ignored(self, monkeypatch):
        from main import client_identity

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        spoofed = _FakeRequest({"cf-connecting-ip": "10.0.0.1"}, peer="192.0.2.9")

        assert client_identity(spoofed) == "192.0.2.9", "peer must win over an unproven header"

    def test_header_is_honoured_when_the_edge_secret_matches(self, monkeypatch):
        from main import client_identity

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        real = _FakeRequest(
            {"cf-connecting-ip": "203.0.113.7", "x-ff-edge-auth": "s3cret"}, peer="192.0.2.9"
        )

        assert client_identity(real) == "203.0.113.7"

    def test_wrong_secret_is_ignored(self, monkeypatch):
        from main import client_identity

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        wrong = _FakeRequest(
            {"cf-connecting-ip": "203.0.113.7", "x-ff-edge-auth": "nope"}, peer="192.0.2.9"
        )

        assert client_identity(wrong) == "192.0.2.9"

    def test_non_ascii_secret_header_does_not_raise(self, monkeypatch):
        """hmac.compare_digest raises TypeError on a str holding non-ASCII."""
        from main import client_identity

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        weird = _FakeRequest(
            {"cf-connecting-ip": "203.0.113.7", "x-ff-edge-auth": "sécret"}, peer="192.0.2.9"
        )

        assert client_identity(weird) == "192.0.2.9"

    def test_unset_secret_falls_back_to_peer(self, monkeypatch):
        from main import client_identity

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "")
        req = _FakeRequest({"cf-connecting-ip": "203.0.113.7"}, peer="192.0.2.9")

        assert client_identity(req) == "192.0.2.9"

    def test_rotating_the_header_no_longer_mints_fresh_buckets(self, monkeypatch, rate_limited_client):
        """The attack from the issue, end to end."""
        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        codes = []
        for i in range(6):
            resp = rate_limited_client.post(
                "/api/pdf/convert-to-word",
                headers={"CF-Connecting-IP": f"10.0.0.{i}"},   # a different lie each time
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
            codes.append(resp.status_code)

        assert 429 in codes, codes
        assert codes.count(429) == 4, codes


class TestCountryIsNotClientControlled:
    def test_unauthenticated_country_is_dropped(self, monkeypatch):
        from main import _client_country

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "s3cret")
        assert _client_country(_FakeRequest({"cf-ipcountry": "ZZ"})) is None

    def test_junk_country_is_dropped_even_from_the_edge(self, monkeypatch):
        from main import _client_country

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "")
        assert _client_country(_FakeRequest({"cf-ipcountry": "'; DROP TABLE--"})) is None
        assert _client_country(_FakeRequest({"cf-ipcountry": "INDIA"})) is None
        assert _client_country(_FakeRequest({"cf-ipcountry": ""})) is None

    def test_unauthenticated_country_is_dropped_when_unset(self, monkeypatch):
        from main import _client_country

        monkeypatch.setattr("main.EDGE_AUTH_SECRET", "")
        assert _client_country(_FakeRequest({"cf-ipcountry": "in"})) is None
        assert _client_country(_FakeRequest({"cf-ipcountry": "T1"})) is None


# ---------------------------------------------------------------------------
# Routes outside /api/ (issue #74)
# ---------------------------------------------------------------------------

class TestNonApiPrefixesAreLimited:
    def test_premium_and_admin_prefixes_are_covered(self):
        from main import RATE_LIMIT_PREFIXES

        for prefix in ("/api/", "/premium/", "/admin/", "/checkout"):
            assert prefix in RATE_LIMIT_PREFIXES

    def test_batch_ocr_is_a_heavy_path(self):
        assert "/premium/batch-ocr" in RATE_LIMIT_HEAVY_PATHS

    def test_a_mounted_premium_route_is_throttled(self, rate_limited_client):
        """The public app has no /premium route; server.py mounts one onto it.

        Register a stand-in on the same app so the middleware sees the path it
        would see in the private deploy — the 404 the bare public app returns
        would pass the assertions vacuously.
        """
        from main import app

        @app.get("/premium/jobs/{job_id}")
        async def _stub(job_id: str):        # pragma: no cover - exercised via HTTP
            return {"id": job_id}

        try:
            codes = [
                rate_limited_client.get("/premium/jobs/1", headers={"CF-Connecting-IP": "203.0.113.44"}).status_code
                for _ in range(6)
            ]
        finally:
            app.router.routes[:] = [
                r for r in app.router.routes if getattr(r, "path", None) != "/premium/jobs/{job_id}"
            ]

        # light limit is 4 in this fixture
        assert codes[:4] == [200, 200, 200, 200], codes
        assert codes[4:] == [429, 429], codes


class TestHeavyTierIsCappedIndependentlyOfIdentity:
    """Whatever identity a flood claims, the box still runs N heavy jobs at once."""

    def test_gate_refuses_past_the_ceiling_and_recovers(self):
        from main import _InFlightGate

        gate = _InFlightGate(2)
        assert gate.acquire()
        assert gate.acquire()
        assert not gate.acquire(), "third concurrent heavy job must be refused"

        gate.release()
        assert gate.acquire(), "a finished job must free its slot"

    def test_zero_disables_the_gate(self):
        from main import _InFlightGate

        gate = _InFlightGate(0)
        assert all(gate.acquire() for _ in range(50))

    def test_saturated_gate_returns_503_not_429(self, rate_limited_client):
        from main import app, _InFlightGate

        previous = app.state.heavy_gate
        app.state.heavy_gate = _InFlightGate(0)
        app.state.heavy_gate.acquire = lambda: False    # pretend it is saturated
        try:
            resp = rate_limited_client.post(
                "/api/pdf/convert-to-word",
                headers={"CF-Connecting-IP": "203.0.113.55"},
                files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            )
        finally:
            app.state.heavy_gate = previous

        assert resp.status_code == 503
        assert resp.headers["Retry-After"] == "5"

    def test_light_requests_are_not_gated(self, rate_limited_client):
        from main import app, _InFlightGate

        previous = app.state.heavy_gate
        gate = _InFlightGate(1)
        gate.acquire()          # fully saturated
        app.state.heavy_gate = gate
        try:
            resp = rate_limited_client.post("/api/pdf/remove-password", files={}, data={})
        finally:
            app.state.heavy_gate = previous

        assert resp.status_code != 503


class TestLimiterStateIsBounded:
    """defaultdict(deque) grew one entry per key seen since boot, forever."""

    def test_prune_drops_drained_keys(self):
        limiter = SlidingWindowRateLimiter(window_seconds=0.1)
        for i in range(200):
            limiter.check(f"ip{i}:light", 5)
        assert len(limiter._hits) == 200

        import time as _time
        _time.sleep(0.15)
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
        limiter = SlidingWindowRateLimiter(window_seconds=0.1)
        limiter.check("transient:light", 5)

        import time as _time
        _time.sleep(0.15)
        limiter.check("transient:light", 5)   # drains the deque, re-adds one hit
        _time.sleep(0.15)

        assert limiter.prune() == 1
        assert limiter._hits == {}

    def test_map_is_capped_between_prunes(self):
        """prune() only runs every 900s; a key-rotating flood grew it until then."""
        limiter = SlidingWindowRateLimiter(window_seconds=60, max_keys=50)
        for i in range(500):
            limiter.check(f"spoofed{i}:heavy", 5)

        assert len(limiter._hits) <= 50

    def test_eviction_prefers_the_least_recently_seen(self):
        import time
        limiter = SlidingWindowRateLimiter(window_seconds=60, max_keys=3)
        for key in ("a:light", "b:light", "c:light"):
            limiter.check(key, 5)
        time.sleep(0.02)
        limiter.check("a:light", 5)      # a is now the most recent
        limiter.check("d:light", 5)      # forces one eviction

        assert "a:light" in limiter._hits
        assert "d:light" in limiter._hits
        assert "b:light" not in limiter._hits


class TestMultiWorkerGuard:
    def test_boot_refuses_multiple_workers(self, monkeypatch):
        from main import _assert_single_worker

        monkeypatch.setenv("WEB_CONCURRENCY", "4")
        monkeypatch.delenv("ALLOW_MULTI_WORKER", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        with pytest.raises(RuntimeError, match="single worker"):
            _assert_single_worker()

    def test_single_worker_and_explicit_opt_out_are_fine(self, monkeypatch):
        from main import _assert_single_worker

        monkeypatch.setenv("WEB_CONCURRENCY", "1")
        _assert_single_worker()

        monkeypatch.setenv("WEB_CONCURRENCY", "4")
        monkeypatch.setenv("ALLOW_MULTI_WORKER", "1")
        _assert_single_worker()

    def test_redis_url_allows_multiple_workers(self, monkeypatch):
        from main import _assert_single_worker

        monkeypatch.setenv("WEB_CONCURRENCY", "4")
        monkeypatch.delenv("ALLOW_MULTI_WORKER", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        _assert_single_worker()


class _FakePipe:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def zremrangebyscore(self, key, lo, hi):
        self.ops.append(("zremrangebyscore", key, lo, hi))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def execute(self):
        out = []
        for op in self.ops:
            if op[0] == "zremrangebyscore":
                out.append(self.store.zremrangebyscore(op[1], op[2], op[3]))
            elif op[0] == "zcard":
                out.append(self.store.zcard(op[1]))
        self.ops = []
        return out


class FakeRedis:
    def __init__(self):
        self.data = {}

    def pipeline(self):
        return _FakePipe(self)

    def zremrangebyscore(self, key, lo, hi):
        lo_n = float("-inf") if lo == "-inf" else float(lo)
        hi_n = float(hi)
        members = [(s, m) for s, m in self.data.get(key, []) if not (lo_n <= s <= hi_n)]
        self.data[key] = members
        return 1

    def zcard(self, key):
        return len(self.data.get(key, []))

    def zadd(self, key, mapping):
        bucket = self.data.setdefault(key, [])
        for member, score in mapping.items():
            bucket.append((float(score), member))
        return len(mapping)

    def zrange(self, key, start, end, withscores=False):
        items = sorted(self.data.get(key, []), key=lambda x: x[0])
        sliced = items[start : end + 1 if end != -1 else None]
        if withscores:
            return [(m, s) for s, m in sliced]
        return [m for _, m in sliced]

    def expire(self, key, _ttl):
        return True

    def scan_iter(self, match=None):
        prefix = (match or "*").rstrip("*")
        for key in list(self.data):
            if key.startswith(prefix):
                yield key

    def delete(self, key):
        self.data.pop(key, None)


class TestRedisSlidingWindowRateLimiter:
    def test_blocks_over_limit_like_the_memory_limiter(self):
        limiter = RedisSlidingWindowRateLimiter(FakeRedis(), window_seconds=60)
        for _ in range(3):
            allowed, _ = limiter.check("ip1:light", 3)
            assert allowed
        allowed, retry_after = limiter.check("ip1:light", 3)
        assert not allowed
        assert retry_after >= 1

    def test_keys_are_independent(self):
        limiter = RedisSlidingWindowRateLimiter(FakeRedis(), window_seconds=60)
        for _ in range(3):
            limiter.check("ip1:light", 3)
        allowed, _ = limiter.check("ip2:light", 3)
        assert allowed

    def test_build_rate_limiter_defaults_to_memory(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        limiter = build_rate_limiter()
        assert isinstance(limiter, SlidingWindowRateLimiter)
