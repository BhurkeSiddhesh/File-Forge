// Runtime API base configuration.
//
// On the web the frontend is served same-origin as the backend, so relative
// paths ("/api/...") just work and API_BASE stays empty. Inside the Capacitor
// mobile app the web assets are loaded from capacitor://localhost (iOS) or
// http://localhost (Android), so relative paths would resolve to the device
// instead of the server — there we need an absolute origin.
//
// The mobile bundle build (mobile/build-web.mjs) rewrites the placeholder below
// to the production API origin. On the web it is left as-is and detection falls
// through to the same-origin (empty) case.
(function () {
  // Placeholder replaced at bundle-build time for the mobile app. If it still
  // contains the mustache token, it was not substituted (i.e. we are on web).
  var BUNDLED_API_BASE = "{{API_BASE}}";

  function isNativeApp() {
    try {
      if (window.Capacitor && typeof window.Capacitor.isNativePlatform === "function") {
        return window.Capacitor.isNativePlatform();
      }
    } catch (e) {}
    var origin = window.location.origin || "";
    return origin.indexOf("capacitor://") === 0 || origin === "http://localhost" || origin === "https://localhost";
  }

  var base = "";
  if (isNativeApp() && BUNDLED_API_BASE.indexOf("{{") !== 0) {
    base = BUNDLED_API_BASE.replace(/\/+$/, "");
  }

  window.API_BASE = base;
  window.apiUrl = function (path) {
    if (!path) return window.API_BASE;
    // Absolute URLs pass through untouched.
    if (/^https?:\/\//i.test(path)) return path;
    return window.API_BASE + path;
  };
})();
