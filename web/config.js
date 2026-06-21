// Backend API base URL. Set it once in the app's "API" field (saved in your
// browser), or hardcode your deployed FastAPI URL here.
window.FRESHMIX_API = (localStorage.getItem("freshmix_api") || "http://localhost:8000")
  .replace(/\/+$/, "");
