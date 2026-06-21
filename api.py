"""FreshMix AI — HTTP API (Phase 3 backend boundary).

The same backend (freshmix.service) exposed over versioned REST. This is the
production split of the in-process call graph the Streamlit app uses today.

Run:  uvicorn api:app --port 8000     (or: python -m uvicorn api:app --port 8000)
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from freshmix import generate_queue, refresh_track
from freshmix.schemas import Queue

DATA = Path(__file__).resolve().parent / "data"
app = FastAPI(title="FreshMix AI API", version="1.0.0")


class GenerateBody(BaseModel):
    free_text: str = ""
    moods: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    freshness: int = 70
    recent_track_ids: list[str] = Field(default_factory=list)
    saved_track_ids: list[str] = Field(default_factory=list)
    taste_genres: list[str] = Field(default_factory=list)
    taste_artists: list[str] = Field(default_factory=list)
    taste_vector: dict = Field(default_factory=dict)


class FeedbackBody(GenerateBody):
    action: str                       # save | skip | refresh
    track_id: str
    exclude: list[str] = Field(default_factory=list)


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "freshmix", "version": app.version}


@app.get("/v1/evidence")
def evidence() -> dict:
    p = DATA / "evidence.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@app.get("/v1/agent/status")
def agent_status() -> dict:
    from freshmix.agent import validate, SKILL_VERSION
    ok, detail = validate()
    return {"claude_active": ok, "mode": "claude" if ok else "rule-based fallback",
            "detail": detail, "model": __import__("config").CONFIG.model,
            "skill_version": SKILL_VERSION}


@app.get("/v1/agent/skill")
def agent_skill() -> dict:
    from freshmix import skill
    return skill.manifest()


@app.post("/v1/freshmix/generate", response_model=Queue)
def generate(body: GenerateBody) -> Queue:
    return generate_queue(
        free_text=body.free_text, moods=body.moods, activities=body.activities,
        freshness=body.freshness, recent=body.recent_track_ids,
        saved=body.saved_track_ids, taste_genres=body.taste_genres,
        taste_artists=body.taste_artists, taste_vector=body.taste_vector,
    )


@app.post("/v1/freshmix/feedback")
def feedback(body: FeedbackBody) -> dict:
    nxt = None
    if body.action in ("skip", "refresh"):
        nxt = refresh_track(
            free_text=body.free_text, moods=body.moods, activities=body.activities,
            freshness=body.freshness, recent=body.recent_track_ids,
            saved=body.saved_track_ids, taste_genres=body.taste_genres,
            taste_artists=body.taste_artists, taste_vector=body.taste_vector,
            exclude=body.exclude,
        )
    return {"ok": True, "action": body.action, "track_id": body.track_id,
            "next": nxt.model_dump() if nxt else None}
