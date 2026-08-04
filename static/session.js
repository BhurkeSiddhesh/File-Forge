// Signed-in session bootstrap for the public app.
//
// The ad-free gate in the AdSense head script (public/main.py
// `_build_adsense_head`) asks "is this visitor entitled to no ads?" by calling
// GET /api/me with a bearer token read from `window.__ffSession`. Nothing used
// to set that global: the only page that signs anyone in is /checkout, and it
// kept its Supabase session to itself. So "Ad-Free Forever" — a permanent,
// paid-for entitlement — was correct in the database, correct in /api/me, and
// completely invisible to the app that shows the ads. This file is the missing
// consumer.
//
// It deliberately does NOT load the Supabase SDK. Every page on the site would
// pay for that, to answer a question that only matters for the small number of
// visitors who have bought something. Instead the auth layer (the checkout
// page, which already runs a full Supabase client) writes the session through
// to a localStorage record this file owns:
//
//   ff_session  {access_token, refresh_token, expires_at}   expires_at = unix SECONDS
//   ff_ad_free  {v: true, exp}                              exp = unix MILLISECONDS
//
// `ff_ad_free` caches only the *positive* answer, and only for a week. That is
// what keeps the gate honest without a token on hand: an expired access token
// no longer means "show this customer ads again". A negative answer is never
// cached, so a purchase takes effect on the very next page load.
(function () {
  var SESSION_KEY = "ff_session";
  var AD_FREE_KEY = "ff_ad_free";
  // Treat a token expiring within a minute as already expired — the /api/me
  // round trip has to finish inside the window.
  var CLOCK_SKEW_SECONDS = 60;
  var AD_FREE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

  function readJson(key) {
    try {
      var raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      // Private-mode Safari and blocked third-party storage both throw here.
      return null;
    }
  }

  function writeJson(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {}
  }

  function nowSeconds() {
    return Math.floor(Date.now() / 1000);
  }

  function isFresh(record) {
    return !!(
      record &&
      record.access_token &&
      typeof record.expires_at === "number" &&
      record.expires_at - CLOCK_SKEW_SECONDS > nowSeconds()
    );
  }

  /* ---- Write-through API used by the auth layer --------------------------- */

  // `session` is a Supabase session object (or null on sign-out). Only the three
  // fields above are kept — nothing here needs the user object, and not storing
  // it keeps the record free of anything worth stealing beyond the token itself.
  window.__ffSetSession = function (session) {
    if (!session || !session.access_token) {
      window.__ffClearSession();
      return;
    }
    var record = {
      access_token: session.access_token,
      refresh_token: session.refresh_token || null,
      expires_at: session.expires_at || nowSeconds() + (session.expires_in || 3600),
    };
    writeJson(SESSION_KEY, record);
    window.__ffSession = { access_token: record.access_token };
  };

  window.__ffClearSession = function () {
    writeJson(SESSION_KEY, null);
    // Sign-out drops the cached entitlement too: the next visitor on this
    // browser may be a different person, and an ad-free site is not theirs.
    writeJson(AD_FREE_KEY, null);
    window.__ffSession = null;
  };

  /* ---- Ad-free answer cache ---------------------------------------------- */

  // true  → known ad-free, no token needed
  // null  → unknown, the gate should ask /api/me if it can
  window.__ffAdFreeHint = function () {
    var cached = readJson(AD_FREE_KEY);
    if (cached && cached.v === true && typeof cached.exp === "number" && cached.exp > Date.now()) {
      return true;
    }
    return null;
  };

  window.__ffCacheAdFree = function (adFree) {
    writeJson(AD_FREE_KEY, adFree ? { v: true, exp: Date.now() + AD_FREE_TTL_MS } : null);
  };

  /* ---- One-time adoption of a session the SDK already had ----------------- */

  // The write-through above only sees sign-ins that happen after this file
  // ships. Anyone who signed in on /checkout before that has a live session
  // sitting in supabase-js's own storage and no `ff_session` record — and would
  // keep seeing ads until they happened to visit /checkout again, which is
  // precisely the "no workaround for the customer" shape of the original bug.
  //
  // supabase-js v2 persists under `sb-<project-ref>-auth-token`. The ref is
  // discovered by scanning for that pattern rather than by fetching the project
  // URL, so this stays synchronous and the fast path below keeps its no-ad-flash
  // guarantee. Read once and copied into our own record; after that the
  // write-through is the only writer.
  function adoptSupabaseSdkSession() {
    var raw = null;
    try {
      for (var i = 0; i < window.localStorage.length; i++) {
        var key = window.localStorage.key(i);
        if (key && /^sb-.+-auth-token$/.test(key)) {
          raw = window.localStorage.getItem(key);
          break;
        }
      }
    } catch (e) {
      return null;  // storage blocked (private-mode Safari, etc.)
    }
    if (!raw) return null;

    try {
      // Newer supabase-js writes `base64-<b64 of the JSON>`; older writes plain
      // JSON. Both shapes are in the wild on returning visitors.
      if (raw.indexOf("base64-") === 0) {
        raw = decodeURIComponent(escape(window.atob(raw.slice(7))));
      }
      var session = JSON.parse(raw);
      // Some versions nest it under `currentSession`.
      if (session && session.currentSession) session = session.currentSession;
      if (!session || !session.access_token) return null;
      var record = {
        access_token: session.access_token,
        refresh_token: session.refresh_token || null,
        expires_at: session.expires_at || 0,
      };
      writeJson(SESSION_KEY, record);
      return record;
    } catch (e) {
      return null;
    }
  }

  /* ---- Bootstrap ---------------------------------------------------------- */

  // Pages that run a full Supabase client of their own (the checkout page) set
  // window.__ffAuthOwner before loading this file. There this file is only the
  // write-through API above: the SDK owns reading and refreshing the session,
  // and a second refresher racing it against rotating refresh tokens is exactly
  // the kind of thing that logs people out.
  if (window.__ffAuthOwner) return;

  var stored = readJson(SESSION_KEY) || adoptSupabaseSdkSession();

  // Synchronous, so the gate — which runs on DOMContentLoaded — sees the token
  // on its first pass and a paying customer never gets an ad flash.
  window.__ffSession = isFresh(stored) ? { access_token: stored.access_token } : null;

  if (window.__ffSession || !stored || !stored.refresh_token) return;

  // The stored access token has expired. Supabase refresh tokens are long-lived
  // and this is the documented GoTrue REST call the SDK itself makes, so we can
  // renew without pulling the SDK onto every page. Best-effort: any failure
  // leaves __ffSession null and the visitor simply sees ads, which is the
  // pre-existing behaviour, not a regression.
  var apiUrl = window.apiUrl || function (p) { return p; };

  fetch(apiUrl("/api/auth/config"))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (cfg) {
      if (!cfg || !cfg.supabase_url || !cfg.supabase_anon_key) return null;
      return fetch(cfg.supabase_url.replace(/\/+$/, "") + "/auth/v1/token?grant_type=refresh_token", {
        method: "POST",
        headers: { "Content-Type": "application/json", apikey: cfg.supabase_anon_key },
        body: JSON.stringify({ refresh_token: stored.refresh_token }),
      }).then(function (r) {
        // 400/401 means the refresh token is spent or revoked — the session is
        // genuinely over, so drop it rather than retrying it on every page.
        if (!r.ok) {
          window.__ffClearSession();
          return null;
        }
        return r.json();
      });
    })
    .then(function (renewed) {
      if (!renewed || !renewed.access_token) return;
      window.__ffSetSession(renewed);
      // The gate has already resolved "show ads" by now; re-running it is what
      // turns them back off. It is idempotent and exposed for exactly this.
      if (typeof window.__ffConsentInit === "function") window.__ffConsentInit();
    })
    .catch(function () {});
})();
