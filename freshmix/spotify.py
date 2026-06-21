"""Real songs via the Spotify Web API (MUSIC_SOURCE=spotify).

Client-credentials flow (no user login): Search for candidates, Artists for
genres, and Audio Features for the taste vector. Needs SPOTIFY_CLIENT_ID /
SPOTIFY_CLIENT_SECRET (free at developer.spotify.com). Returns [] on missing
creds / network / errors so the recommender falls back to iTunes or the mock
catalog.

Note: Spotify deprecated `audio-features` for apps without extended access
(Nov 2024) — a 403 there is handled gracefully (we fall back to mood-approx
features), so search-based discovery still works for any app.
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import time
import urllib.parse
import urllib.request

from .music import _ACTIVITY_TERMS, _MOOD_AUDIO, _MOOD_TERMS
from .schemas import Track

_YEAR = datetime.date.today().year
_tok = {"v": None, "exp": 0.0}


def _creds():
    return os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")


def available() -> bool:
    return all(_creds())


def _token() -> str:
    if _tok["v"] and time.time() < _tok["exp"]:
        return _tok["v"]
    cid, sec = _creds()
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=data,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        j = json.loads(r.read().decode("utf-8"))
    _tok["v"] = j["access_token"]
    _tok["exp"] = time.time() + j.get("expires_in", 3600) - 60
    return _tok["v"]


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _search(term: str, token: str, limit: int = 8) -> list:
    q = urllib.parse.urlencode({"q": term, "type": "track", "limit": limit})
    return _get("https://api.spotify.com/v1/search?" + q, token).get(
        "tracks", {}).get("items", [])


def _artist_genres(ids: list[str], token: str) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        try:
            data = _get("https://api.spotify.com/v1/artists?ids="
                        + ",".join(ids[i:i + 50]), token)
        except Exception:
            continue
        for a in data.get("artists", []):
            if a:
                gs = a.get("genres") or []
                out[a["id"]] = gs[0].title() if gs else "Music"
    return out


def _audio_features(ids: list[str], token: str) -> dict:
    out = {}
    for i in range(0, len(ids), 100):
        try:
            data = _get("https://api.spotify.com/v1/audio-features?ids="
                        + ",".join(ids[i:i + 100]), token)
        except Exception:
            return {}                       # deprecated / 403 -> use mood-approx features
        for f in data.get("audio_features", []) or []:
            if f and f.get("id"):
                out[f["id"]] = {"energy": f.get("energy", 0.5),
                                "valence": f.get("valence", 0.5),
                                "tempo": int(f.get("tempo", 110))}
    return out


def _track(t: dict, moods, activities, genre: str, feat: dict | None) -> Track | None:
    name = t.get("name")
    artists = t.get("artists") or []
    if not name or not artists:
        return None
    album = t.get("album") or {}
    year = int((album.get("release_date") or "0")[:4] or 0)
    primary = moods[0] if moods else "Chill"
    en, val, tempo = _MOOD_AUDIO.get(primary, (0.5, 0.55, 110))
    if feat:
        en, val, tempo = feat["energy"], feat["valence"], feat["tempo"]
    imgs = album.get("images") or []
    return Track(
        id=f"sp{t.get('id')}", name=name, artist=artists[0].get("name", "Unknown"),
        genre=genre or "Music", year=year or _YEAR, new_artist=year >= _YEAR - 1,
        moods=list(moods) or [primary], activities=list(activities),
        energy=en, valence=val, tempo=tempo,
        artwork_url=(imgs[0]["url"] if imgs else None),
        preview_url=t.get("preview_url"),
        url=(t.get("external_urls") or {}).get("spotify"),
    )


def live_candidates(moods, activities, limit: int = 48, seeds=None,
                    artist_seeds=None) -> list[Track]:
    if not available():
        return []
    try:
        token = _token()
    except Exception:
        return []

    terms = list(artist_seeds or [])[:2] + list(seeds or [])[:3]
    for m in (moods or []):
        terms += _MOOD_TERMS.get(m, [])[:2]
    for a in (activities or []):
        terms += _ACTIVITY_TERMS.get(a, [])[:1]
    if not terms:
        terms = ["new music", "fresh indie", "popular"]

    raw, seen = [], set()
    for term in terms:
        try:
            items = _search(term, token, 8)
        except Exception:
            continue
        for t in items:
            if t and t.get("id") and t["id"] not in seen:
                seen.add(t["id"])
                raw.append(t)
        if len(raw) >= limit:
            break
    if not raw:
        return []

    artist_ids = list({(t["artists"][0]["id"]) for t in raw
                       if t.get("artists") and t["artists"][0].get("id")})
    genres = _artist_genres(artist_ids, token)
    feats = _audio_features([t["id"] for t in raw], token)

    out = []
    for t in raw:
        aid = t["artists"][0].get("id") if t.get("artists") else None
        tr = _track(t, moods, activities, genres.get(aid, "Music"), feats.get(t["id"]))
        if tr:
            out.append(tr)
    return out
