// Backend API base URL resolution order:
//   1. ?api=<url> query param (also saved for next visit)
//   2. saved value from the in-app "API" button (localStorage)
//   3. hardcoded fallback below (localhost for dev)
(function () {
  const clean = (u) => u.replace(/\/+$/, "");
  const fromParam = new URLSearchParams(location.search).get("api");
  if (fromParam) localStorage.setItem("freshmix_api", clean(fromParam));
  window.FRESHMIX_API = clean(localStorage.getItem("freshmix_api") || "http://localhost:8000");
})();
