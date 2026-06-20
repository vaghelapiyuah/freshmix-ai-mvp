# FreshMix AI — MVP

The product solution to Spotify's discovery problem: turn **mood, activity,
language, and a freshness dial** into a **fresh-but-familiar** queue the user can
trust. Built on the evidence from the Review Discovery Engine
(`spotify-discovery-engine-cgdz6f8vcaxrmskv6gbtze.streamlit.app`).

Runs **fully offline** (mock catalog + rule-based agent) — no API keys needed.
Add `ANTHROPIC_API_KEY` to enable Claude-written "why this song" rationale.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
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
