# FreshMix AI — Deployment (Phase 6)

Frontend and backend deploy independently. Locally, `docker compose` runs both.

## Local (both services, one command)
```bash
docker compose up --build
# API → http://localhost:8000  (docs /docs)   UI → http://localhost:8501 (wired to api)
```
No keys needed (offline mode). Set `ANTHROPIC_API_KEY` to enable the Claude path.

## Backend (FastAPI) — production
- **Container:** `Dockerfile` → `uvicorn api:app --host 0.0.0.0 --port $PORT`.
- **Platforms:** Render / Fly / Cloud Run. Render blueprint: `render.yaml`
  (health check `/v1/health`). Heroku-style: `Procfile`.
- **Autoscale** on RPS; long jobs (bulk rationale, nightly insight refresh) move
  to a worker queue + Anthropic Batches API.
- **Secrets:** `ANTHROPIC_API_KEY` in the platform's secret store (never in git;
  `.env` is gitignored).

## Frontend
- **PM/analyst dashboard (Streamlit):** push to GitHub `main` → deploy on
  Streamlit Community Cloud (main file `app.py`); set `FRESHMIX_API_URL` (to the
  deployed API) and `ANTHROPIC_API_KEY` in app Secrets. `.streamlit/config.toml`
  is included.
- **Consumer mobile feature:** build → TestFlight / Play Internal → staged
  rollout behind a feature flag.

## CI/CD
- `.github/workflows/ci.yml` — installs deps and runs the offline test suite on
  every push/PR (zero keys, zero tokens).
- Deploy on merge to `main` (Render/Streamlit auto-deploy from the repo).
- Blue-green for the API; dashboards for token cost, p95 latency, skip-rate.

## Done-when
A merge to `main` runs CI green, ships the API, and redeploys the dashboard.

## Endpoints (smoke test after deploy)
```
GET  /v1/health
GET  /v1/agent/status        # claude vs rule-based + skill version
GET  /v1/agent/skill         # skill manifest
POST /v1/freshmix/generate   # {moods, activities, freshness, ...} -> Queue
POST /v1/freshmix/feedback   # {action, track_id, ...} -> {ok, next}
```
