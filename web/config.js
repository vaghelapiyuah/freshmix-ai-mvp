// Backend API base URL resolution order:
//   1. ?api=<url> query param (also saved for next visit)
//   2. saved value from the in-app "API" button (localStorage)
//   3. deployed Render backend (default below) — so the bare URL just works
//      (for local dev, open with ?api=http://localhost:8000)
(function () {
  const clean = (u) => u.replace(/\/+$/, "");
  const DEFAULT_API = "https://freshmix-api-nvea.onrender.com";
  const fromParam = new URLSearchParams(location.search).get("api");
  if (fromParam) localStorage.setItem("freshmix_api", clean(fromParam));
  window.FRESHMIX_API = clean(localStorage.getItem("freshmix_api") || DEFAULT_API);
})();
