"""RAG service — load the Phase 0 review-insight corpus and turn it into
'avoid signals' that steer the recommender away from real pain points.

The corpus (data/review_insights.jsonl) is produced by phase0_evidence.py from
the deployed engine's analysis. If it's missing, signals are zero and the
recommender behaves normally (graceful).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CORPUS = Path(__file__).resolve().parent.parent / "data" / "review_insights.jsonl"

_REPETITION = {"same_songs_repeated", "same_artists_repeated"}
_REPETITION_THEMES = {"repetitive_recommendations", "playlist_fatigue",
                      "algorithm_over_personalization"}
_MOOD = {"wrong_mood"}
_MOOD_THEMES = {"poor_mood_understanding"}
_SEV = {"low": 1, "medium": 2, "high": 3}


@lru_cache(maxsize=1)
def load_corpus() -> tuple[dict, ...]:
    if not _CORPUS.exists():
        return ()
    rows = []
    for line in _CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return tuple(rows)


def retrieve(moods: list[str], activities: list[str], free_text: str, k: int = 3) -> list[dict]:
    """Most relevant pain points for this request (for display + targeting)."""
    corpus = load_corpus()
    if not corpus:
        return []
    terms = {w.lower() for w in (free_text or "").split()} | {m.lower() for m in moods} \
        | {a.lower() for a in activities}
    scored = []
    for row in corpus:
        text = (row.get("example_text", "") + " " + row.get("theme", "")).lower()
        overlap = sum(1 for t in terms if t and t in text)
        score = _SEV.get(row.get("severity", "low"), 1) + 2 * overlap
        scored.append((score, row))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [r for _, r in scored[:k]]


def avoid_signals() -> dict:
    """Global pain-point profile → behavioral weights for the recommender."""
    corpus = load_corpus()
    n = len(corpus)
    if not n:
        return {"repetition": 0.0, "mood": 0.0, "explain": True, "n": 0}
    rep = sum(1 for r in corpus
              if r.get("frustration") in _REPETITION or r.get("theme") in _REPETITION_THEMES)
    mood = sum(1 for r in corpus
               if r.get("frustration") in _MOOD or r.get("theme") in _MOOD_THEMES)
    return {
        "repetition": round(rep / n, 3),     # drives genre diversity + strict anti-repeat
        "mood": round(mood / n, 3),          # drives enforced mood match
        "explain": True,                     # low-trust → always show 'why this song'
        "n": n,
    }
