"""Agent layer (Phase 4) — Claude intent parsing + per-track rationale.

Two agent steps, each with a rule-based fallback so the feature degrades, never
dies:
  A. parse_intent  — free text + chips -> structured DiscoveryRequest
  B. rationale     — per-track "why this song"

Claude is used when ANTHROPIC_API_KEY is present and reachable (validate());
otherwise the rule-based paths run. The client is injectable for testing.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from config import ACTIVITIES, CONFIG, MOODS
from . import skill as _skill
from .schemas import DiscoveryRequest, Track

# The agent's system prompt now comes from the packaged, versioned Agent Skill
# (skill/freshmix-discovery/SKILL.md), not an inline string.
_SKILL = _skill.load()
FRESHMIX_SKILL = _SKILL.system
SKILL_VERSION = _SKILL.version

_LANGS = {"hindi": "hi", "spanish": "es", "french": "fr", "english": "en",
          "korean": "ko", "japanese": "ja"}


class ParsedIntent(BaseModel):
    """Structured-output schema for Claude intent parsing."""
    moods: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    freshness: int = 70
    language: str = "en"


# --- client + preflight ----------------------------------------------------- #
def _client():
    import anthropic
    return anthropic.Anthropic()


def validate() -> tuple[bool, str]:
    """Cheap preflight so callers can fall back cleanly instead of 401-ing."""
    if not CONFIG.has_api_key:
        return False, "No ANTHROPIC_API_KEY — using rule-based agent."
    try:
        import anthropic
        _client().messages.create(model=CONFIG.model, max_tokens=1,
                                  messages=[{"role": "user", "content": "ping"}])
        return True, "ok"
    except anthropic.AuthenticationError:
        return False, "Invalid ANTHROPIC_API_KEY."
    except Exception as e:                       # network / model / rate limit
        return False, f"{type(e).__name__}: {e}"


# --- A. intent parsing ------------------------------------------------------ #
def _rule_parse(free_text, moods, activities, freshness, recent, saved) -> DiscoveryRequest:
    text = (free_text or "").lower()
    moods, activities = list(moods), list(activities)
    m = re.search(r"(\d{1,3})\s*%", text)
    if m and any(w in text for w in ("fresh", "new", "discover")):
        freshness = max(0, min(100, int(m.group(1))))
    for mood in MOODS:
        if mood.lower() in text and mood not in moods:
            moods.append(mood)
    for act in ACTIVITIES:
        if act.lower() in text and act not in activities:
            activities.append(act)
    language = "en"
    for name, code in _LANGS.items():
        if name in text:
            language = code
            break
    return DiscoveryRequest(free_text=free_text, moods=moods, activities=activities,
                            language=language, freshness=freshness,
                            recent_track_ids=recent, saved_track_ids=saved)


def _llm_parse(free_text: str, client=None) -> ParsedIntent | None:
    """Claude structured-output intent parse. Returns None to signal fallback."""
    if client is None and not CONFIG.has_api_key:
        return None
    try:
        client = client or _client()
        prompt = (
            f"Allowed moods: {MOODS}. Allowed activities: {ACTIVITIES}.\n"
            f"User request: \"{free_text}\"\n"
            "Extract mood(s), activity(ies), freshness (0=familiar..100=fresh), "
            "and language code. Use only allowed values for mood/activity."
        )
        resp = client.messages.parse(
            model=CONFIG.model, max_tokens=300, system=FRESHMIX_SKILL,
            messages=[{"role": "user", "content": prompt}],
            output_format=ParsedIntent,
        )
        return resp.parsed_output
    except Exception:
        return None


def parse_intent(free_text, moods, activities, freshness, recent, saved,
                 use_llm: bool | None = None) -> DiscoveryRequest:
    base = _rule_parse(free_text, moods, activities, freshness, recent, saved)
    if use_llm is None:
        use_llm = CONFIG.has_api_key
    if use_llm and (free_text or "").strip():
        pi = _llm_parse(free_text)
        if pi:
            base.moods = sorted(set(base.moods) | {m for m in pi.moods if m in MOODS})
            base.activities = sorted(
                set(base.activities) | {a for a in pi.activities if a in ACTIVITIES})
            if 0 <= pi.freshness <= 100:
                base.freshness = pi.freshness
            if pi.language:
                base.language = pi.language
    return base


# --- B. rationale ----------------------------------------------------------- #
def rationale(track: Track, req: DiscoveryRequest, novel: bool) -> str:
    mood = (req.moods or track.moods or ["your"])[0].lower()
    if novel:
        return f"Fresh pick for your {mood} mood — new {track.genre.lower()} artist, similar energy."
    return f"Keeps your {mood} vibe — familiar {track.genre.lower()} sound you already like."


def llm_rationales(tracks, req, novel_ids, client=None) -> dict[str, str] | None:
    if client is None and not CONFIG.has_api_key:
        return None
    try:
        client = client or _client()
        listing = "\n".join(
            f"{t.id}: {t.name} by {t.artist} ({t.genre}, "
            f"{'new' if t.id in novel_ids else 'familiar'})" for t in tracks
        )
        prompt = (
            f"User wants: mood={req.moods}, activity={req.activities}, "
            f"freshness={req.freshness}%, prompt=\"{req.free_text}\".\n"
            f"Tracks:\n{listing}\n\n"
            "For each track id give one short 'why this song' line as `id: why`."
        )
        resp = client.messages.create(
            model=CONFIG.model, max_tokens=800, system=FRESHMIX_SKILL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        out = {}
        for line in text.splitlines():
            if ":" in line:
                tid, why = line.split(":", 1)
                out[tid.strip()] = why.strip()
        return out or None
    except Exception:
        return None
