// Test harness for the ad-free gate (issue #52).
//
// The gate is inline JS built by main._build_adsense_head(), and its session
// comes from static/session.js. Both used to be asserted with `"__ffSession" in
// head` — a check that passed for the entire period during which nothing set
// that global and every paying customer saw ads. This runs the real scripts
// against a minimal DOM instead and reports what the visitor would actually see.
//
//   node ad_free_gate_harness.js <session.js> <gate.js> <scenario.json>
//
// Scenario: { "localStorage": {...}, "consent": "granted", "me": {...} | null,
//             "meStatus": 200, "authConfig": {...}, "refreshed": {...} }
// Prints a JSON result: { slotsHidden, adsFilled, fetched, localStorage }.
const fs = require('fs');
const vm = require('vm');

const [sessionPath, gatePath, scenarioPath] = process.argv.slice(2);
const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));

const store = new Map(Object.entries(scenario.localStorage || {}));
if (scenario.consent) store.set('ff_consent', scenario.consent);

const slots = [{ style: {} }, { style: {} }];
const ads = [];
for (let i = 0; i < 2; i++) {
  ads.push({
    attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
  });
}

const fetched = [];

function jsonResponse(ok, body) {
  return Promise.resolve({ ok, json: () => Promise.resolve(body) });
}

// The gate and session.js only ever fetch three things; anything else is a bug
// in the code under test, so fail loudly rather than resolving something.
function fakeFetch(url, init) {
  fetched.push(String(url));
  if (String(url).indexOf('/api/me') !== -1) {
    const status = scenario.meStatus || 200;
    return jsonResponse(status === 200, scenario.me || null);
  }
  if (String(url).indexOf('/api/auth/config') !== -1) {
    return jsonResponse(true, scenario.authConfig || null);
  }
  if (String(url).indexOf('grant_type=refresh_token') !== -1) {
    return jsonResponse(!!scenario.refreshed, scenario.refreshed || null);
  }
  return Promise.reject(new Error('unexpected fetch: ' + url));
}

const listeners = {};
const context = {
  console,
  Date,
  Math,
  JSON,
  setTimeout,
  Promise,
  fetch: fakeFetch,
  IntersectionObserver: function (cb) {
    // Report everything as immediately in view: laziness is orthogonal to the
    // question this harness asks, which is whether a fill happens at all.
    this.observe = (el) => cb([{ isIntersecting: true, target: el }], this);
    this.unobserve = () => {};
  },
  localStorage: {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  },
  document: {
    readyState: 'complete',
    addEventListener: (evt, fn) => { (listeners[evt] = listeners[evt] || []).push(fn); },
    querySelectorAll: (sel) => (sel === '.ad-slot' ? slots : ads),
  },
  addEventListener: () => {},
};
context.window = context;
vm.createContext(context);

vm.runInContext(fs.readFileSync(sessionPath, 'utf8'), context, { filename: 'session.js' });
vm.runInContext(fs.readFileSync(gatePath, 'utf8'), context, { filename: 'gate.js' });

// Let the promise chains in both files settle before reporting.
(async () => {
  for (let i = 0; i < 20; i++) await new Promise((r) => setImmediate(r));
  process.stdout.write(JSON.stringify({
    slotsHidden: slots.every((s) => s.style.display === 'none'),
    adsFilled: ads.filter((a) => a.attrs['data-lazy-filled'] === '1').length,
    fetched,
    hasSession: !!(context.__ffSession && context.__ffSession.access_token),
    localStorage: Object.fromEntries(store),
  }));
})();
