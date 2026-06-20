"""Live music source — real songs via the iTunes Search API (no API key).

Returns real tracks (name, artist, genre, year, album art, 30s preview, link).
`MUSIC_SOURCE=mock` forces the offline catalog (used by tests). On any network
failure the recommender falls back to the mock catalog automatically.
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.parse
import urllib.request
from functools import lru_cache

from .schemas import Track

_UA = "Mozilla/5.0 (research; freshmix)"
_YEAR = datetime.date.today().year

_MOOD_TERMS = {
    "Focus": ["lo-fi beats", "focus instrumental", "study music"],
    "Gym": ["workout hip hop", "high energy edm", "pump up"],
    "Chill": ["chillhop", "relax acoustic", "mellow chill"],
    "Travel": ["feel good indie", "roadtrip pop", "sunny indie"],
}
_ACTIVITY_TERMS = {
    "Work": ["deep work instrumental"],
    "Commute": ["upbeat commute pop"],
    "Workout": ["cardio workout edm"],
}
_MOOD_AUDIO = {  # rough energy/valence/tempo per mood
    "Focus": (0.30, 0.50, 90), "Gym": (0.85, 0.65, 135),
    "Chill": (0.35, 0.55, 85), "Travel": (0.60, 0.70, 115),
}


def source() -> str:
    return os.getenv("MUSIC_SOURCE", "itunes").lower()


@lru_cache(maxsize=128)
def _search(term: str, limit: int = 12, country: str = "us") -> tuple:
    q = urllib.parse.urlencode(
        {"term": term, "entity": "song", "limit": limit, "country": country})
    req = urllib.request.Request("https://itunes.apple.com/search?" + q,
                                 headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return tuple(data.get("results", []))


def _to_track(r: dict, moods, activities) -> Track | None:
    name, artist = r.get("trackName"), r.get("artistName")
    if not name or not artist:
        return None
    year = int((r.get("releaseDate") or "0")[:4] or 0)
    primary = (moods[0] if moods else "Chill")
    en, val, tempo = _MOOD_AUDIO.get(primary, (0.5, 0.55, 110))
    art = (r.get("artworkUrl100") or "").replace("100x100", "300x300") or None
    return Track(
        id=f"it{r.get('trackId')}",
        name=name, artist=artist,
        genre=r.get("primaryGenreName") or "Music",
        year=year or _YEAR,
        new_artist=year >= _YEAR - 1,            # recent release = "fresh"
        moods=list(moods) or [primary],
        activities=list(activities),
        energy=en, valence=val, tempo=tempo,
        artwork_url=art, preview_url=r.get("previewUrl"),
        url=r.get("trackViewUrl"),
    )


def live_candidates(moods, activities, limit: int = 48) -> list[Track]:
    """Real tracks for the selected mood/activity. [] on failure -> mock fallback."""
    terms: list[str] = []
    for m in (moods or []):
        terms += _MOOD_TERMS.get(m, [])[:2]
    for a in (activities or []):
        terms += _ACTIVITY_TERMS.get(a, [])[:1]
    if not terms:
        terms = ["new music 2026", "fresh indie", "popular hits"]

    out, seen = [], set()
    for term in terms:
        try:
            results = _search(term)
        except Exception:
            continue                              # skip this term; others may work
        for r in results:
            t = _to_track(r, moods, activities)
            if not t:
                continue
            key = (t.name.lower(), t.artist.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
            if len(out) >= limit:
                return out
    return out
