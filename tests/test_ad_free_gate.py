"""The ad-free gate, exercised rather than string-matched (issue #52).

`lifetime_ad_free` is the flagship web product. It was granted correctly, it
showed up correctly in /api/me — and it removed no ads at all, because the gate
read `window.__ffSession` and nothing in the repo ever set it. The only test
covering the gate asserted that the *string* "__ffSession" appeared in the
generated head, which is true whether or not a session can ever reach it.

These run the two real scripts — static/session.js and the inline gate built by
`main._build_adsense_head()` — against a minimal DOM in node, and assert on what
the visitor would actually see: are the `.ad-slot` boxes hidden, did any ad get
filled. Skipped where node isn't available (CI runners have it).
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_HARNESS = _HERE / "ad_free_gate_harness.js"
_SESSION_JS = _HERE.parent / "static" / "session.js"

_NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(_NODE is None, reason="node not available")

# A token that is valid for another hour / expired an hour ago.
_FRESH_EXP = 4102444800  # 2100-01-01
_STALE_EXP = 1000000000  # 2001-09-09


def _gate_source() -> str:
    """The inline gate script out of the rendered AdSense head."""
    import main

    saved = main.ADSENSE_CLIENT
    try:
        main.ADSENSE_CLIENT = "ca-pub-test"
        head = main._build_adsense_head()
    finally:
        main.ADSENSE_CLIENT = saved

    # The last inline <script> block is the consent/ad-free/lazy-fill gate.
    blocks = re.findall(r"<script>(.*?)</script>", head, re.S)
    assert blocks, "no inline script in the AdSense head"
    return blocks[-1]


def _run(tmp_path, **scenario) -> dict:
    scenario.setdefault("consent", "granted")
    gate = tmp_path / "gate.js"
    gate.write_text(_gate_source(), encoding="utf-8")
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(json.dumps(scenario), encoding="utf-8")

    proc = subprocess.run(
        [_NODE, str(_HARNESS), str(_SESSION_JS), str(gate), str(scenario_file)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _session(access_token="tok_abc", expires_at=_FRESH_EXP, refresh_token=None):
    return json.dumps(
        {"access_token": access_token, "expires_at": expires_at, "refresh_token": refresh_token}
    )


def test_anonymous_visitor_still_sees_ads(tmp_path):
    """The free-launch default: no session anywhere, ads fill as before."""
    result = _run(tmp_path)
    assert result["hasSession"] is False
    assert result["slotsHidden"] is False
    assert result["adsFilled"] == 2
    assert not any("/api/me" in u for u in result["fetched"])


def test_paying_customer_gets_no_ads(tmp_path):
    """The bug this file exists for: a stored session must reach the gate.

    Before the fix `window.__ffSession` was set by nothing, so this scenario —
    signed in, ad_free true in /api/me — still filled every ad slot.
    """
    result = _run(
        tmp_path,
        localStorage={"ff_session": _session()},
        me={"features": {"ad_free": True, "batch_ocr": False}},
    )
    assert result["hasSession"] is True
    assert any("/api/me" in u for u in result["fetched"])
    assert result["slotsHidden"] is True
    assert result["adsFilled"] == 0


def test_signed_in_without_the_entitlement_sees_ads(tmp_path):
    result = _run(
        tmp_path,
        localStorage={"ff_session": _session()},
        me={"features": {"ad_free": False, "batch_ocr": False}},
    )
    assert result["slotsHidden"] is False
    assert result["adsFilled"] == 2
    # A negative is never cached, so a purchase takes effect on the next load.
    assert "ff_ad_free" not in result["localStorage"]


def test_positive_answer_is_cached_for_the_next_visit(tmp_path):
    result = _run(
        tmp_path,
        localStorage={"ff_session": _session()},
        me={"features": {"ad_free": True}},
    )
    cached = json.loads(result["localStorage"]["ff_ad_free"])
    assert cached["v"] is True


def test_expired_token_with_a_cached_entitlement_still_hides_ads(tmp_path):
    """An hour-old access token must not put ads back in front of a customer."""
    result = _run(
        tmp_path,
        localStorage={
            "ff_session": _session(expires_at=_STALE_EXP),
            "ff_ad_free": json.dumps({"v": True, "exp": 4102444800000}),
        },
    )
    assert result["hasSession"] is False
    assert result["slotsHidden"] is True
    assert result["adsFilled"] == 0
    # Answered from cache — no token, so /api/me was never asked.
    assert not any("/api/me" in u for u in result["fetched"])


def test_a_stale_cache_is_not_honoured(tmp_path):
    result = _run(
        tmp_path,
        localStorage={"ff_ad_free": json.dumps({"v": True, "exp": 1000})},
    )
    assert result["slotsHidden"] is False
    assert result["adsFilled"] == 2


def test_expired_token_is_refreshed_and_the_gate_re_runs(tmp_path):
    """Recovering the session must turn the ads back off, not just next time."""
    result = _run(
        tmp_path,
        localStorage={"ff_session": _session(expires_at=_STALE_EXP, refresh_token="rt_1")},
        authConfig={"supabase_url": "https://proj.supabase.co", "supabase_anon_key": "anon"},
        refreshed={"access_token": "tok_new", "refresh_token": "rt_2", "expires_at": _FRESH_EXP},
        me={"features": {"ad_free": True}},
    )
    assert any("grant_type=refresh_token" in u for u in result["fetched"])
    assert result["hasSession"] is True
    assert result["slotsHidden"] is True
    stored = json.loads(result["localStorage"]["ff_session"])
    # The rotated refresh token is written back, or the next load can't renew.
    assert stored["access_token"] == "tok_new"
    assert stored["refresh_token"] == "rt_2"


def test_a_dead_refresh_token_clears_the_session(tmp_path):
    """A revoked/spent refresh token ends the session instead of retrying forever."""
    result = _run(
        tmp_path,
        localStorage={"ff_session": _session(expires_at=_STALE_EXP, refresh_token="rt_dead")},
        authConfig={"supabase_url": "https://proj.supabase.co", "supabase_anon_key": "anon"},
        refreshed=None,
    )
    assert result["hasSession"] is False
    assert "ff_session" not in result["localStorage"]
    assert result["adsFilled"] == 2


def test_no_consent_means_no_fill_regardless(tmp_path):
    """The ad-free gate must not become a way around the consent gate."""
    result = _run(tmp_path, consent="denied")
    assert result["adsFilled"] == 0


def test_gate_loads_the_session_bootstrap(tmp_path):
    """The head must actually ship the file that populates __ffSession."""
    import main

    saved = main.ADSENSE_CLIENT
    try:
        main.ADSENSE_CLIENT = "ca-pub-test"
        head = main._build_adsense_head()
    finally:
        main.ADSENSE_CLIENT = saved

    assert "/static/session.js" in head
    # ...and before the inline gate, which resolves on DOMContentLoaded.
    assert head.index("/static/session.js") < head.index("__ffSession")
