# FreshMix AI — MVP

[![CI](https://github.com/vaghelapiyuah/freshmix-ai-mvp/actions/workflows/ci.yml/badge.svg)](https://github.com/vaghelapiyuah/freshmix-ai-mvp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-1DB954.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)

The product solution to Spotify's discovery problem: turn **mood, activity,
language, and a freshness dial** into a **fresh-but-familiar** queue the user can
trust. Built on the evidence from the Review Discovery Engine
(`spotify-discovery-engine-cgdz6f8vcaxrmskv6gbtze.streamlit.app`).

Runs **fully offline** (mock catalog + rule-based agent) — no API keys needed.
Add `ANTHROPIC_API_KEY` to enable Claude-written "why this song" rationale.

**Music source** (`MUSIC_SOURCE`): `itunes` (real songs, no key — default) ·
`spotify` (real Spotify API — set `SPOTIFY_CLIENT_ID`/`SECRET`; uses audio-features
for the taste vector when the app has access) · `mock` (offline catalog). Any
source falls back gracefully if unavailable.

## Two frontends, one backend

| Frontend | Tech | Host | Talks to |
|---|---|---|---|
| `app.py` | Streamlit (server) | Streamlit Cloud | in-process backend |
| `web/` | static HTML/JS | **Vercel** (or any static host) | FastAPI `api.py` over REST |

The `web/` app is a static SPA — the only Vercel-compatible option (Streamlit needs
a persistent server). It calls the FastAPI backend, so deploy `api.py` somewhere
persistent (Render `render.yaml` is included) and point the web app at it via the
**“API”** button (saved in your browser).

### Deploy the Vercel frontend
1. Deploy the backend first (Render → uses `render.yaml`) and copy its URL, e.g. `https://freshmix-api.onrender.com`.
2. On **vercel.com** → *Add New Project* → import `vaghelapiyuah/freshmix-ai-mvp`.
   `vercel.json` serves the `web/` folder (Framework Preset: **Other**, no build).
3. Open the deployed site → click **API** → paste your backend URL. Done — real songs + personalization.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py                 # Streamlit UI (in-process)

uvicorn api:app --port 8000          # REST backend for the web/ frontend
python -m http.server 5500 -d web    # then open http://localhost:5500
```

Then: pick mood + activity, set the freshness slider, tap **Generate FreshMix**,
and **Save / Skip / Refresh** tracks. Skips and saves feed the next mix.

```bash
pytest            # or:  python tests/test_freshmix.py   (offline, no keys)
```

## How it maps to the build guide (phases)

| Phase | Where |
|---|---|
| P1 Frontend | `app.py` (prompt, chips, freshness, result cards, Save/Skip/Refresh) |
| P2 Backend | `freshmix/recommend.py` (candidates → freshness blend → anti-repeat → guardrails) |
| P3 Linking | `freshmix/service.py` — `generate_queue()` / `refresh_track()` (the API entrypoints) |
| P4 Agent API | `freshmix/agent.py` — Claude rationale (`llm_rationales`) with rule-based fallback |
| P5 Agent Skill | `FRESHMIX_SKILL` prompt + `DiscoveryRequest`/`Queue` schemas (`freshmix/schemas.py`) |
| P7 Tests | `tests/test_freshmix.py` |
| P8 Edge cases | freshness 0/100 guardrails, anti-repeat widening, skip-all bias, offline fallback |

## Design decisions (traced to engine evidence)

- **"Why this song" on every track** ← low trust = 58% of root causes
- **Freshness slider** ← "want control over freshness" theme (7.8%)
- **Anti-repeat filter** ← repetitive theme (11.2%), #1 frustration "bad recs"
- **Mood + activity inputs** ← context mismatch = 16% of root causes
- **Fresh-but-familiar core** ← top unmet need (5.6%)

## Architecture

```
app.py (Streamlit UI)
  └─ freshmix.generate_queue()            # service / API entrypoint
       ├─ agent.parse_intent()            # prompt + chips -> DiscoveryRequest
       ├─ recommend.generate()            # candidates -> blend -> anti-repeat -> rank
       │     └─ catalog.candidates()      # mock catalog (swap for Spotify API)
       └─ agent.rationale / llm_rationales# "why this song" (rule-based or Claude)
  └─ feedback.UserState                   # save / skip / refresh -> next mix
```

Swap `freshmix/catalog.py` for the Spotify API and `agent.llm_rationales` for the
live Claude call to go from MVP to production — the contracts stay the same.
