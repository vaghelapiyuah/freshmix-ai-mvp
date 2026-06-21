"""The recommendation core: candidates -> freshness blend -> anti-repeat ->
RAG-driven guardrails -> ranked queue. Phase 0's review corpus (via rag.py)
actively steers this away from the real pain points.
"""

from __future__ import annotations

from config import CONFIG
from . import agent, catalog as cat, context, music, rag
from .schemas import DiscoveryRequest, Queue, QueueItem, Track


def _relevance(t: Track, req: DiscoveryRequest, fam_genres, fav_artists) -> float:
    score = 0.0
    score += len(set(req.moods) & set(t.moods)) * 2
    score += len(set(req.activities) & set(t.activities))
    score += t.valence * 0.5
    if t.genre in fam_genres:
        score += 2.0                       # suggest by previously listened genres
    if t.artist in fav_artists:
        score += 3.0                       # ...and favourite artists (stronger)
    return score


def _pick(bucket, count, used, gcount, cap):
    out = []
    for t in bucket:
        if len(out) >= count:
            break
        if t.id in used:
            continue
        if cap is not None and gcount.get(t.genre, 0) >= cap:
            continue
        out.append(t)
        used.add(t.id)
        gcount[t.genre] = gcount.get(t.genre, 0) + 1
    return out


def generate(req: DiscoveryRequest, catalog: list[Track] | None = None) -> Queue:
    catalog = catalog or cat.load_catalog()
    n = CONFIG.queue_size
    note = ""

    # RAG: what pain points must we counter? (from the engine's review corpus)
    sig = rag.avoid_signals()
    mood_required = bool(req.moods) and sig["mood"] >= 0.10
    genre_div = sig["repetition"] >= 0.20
    # personalization: prefer genres + artists the user has previously listened to
    fam_genres = set(req.taste_genres) or context.familiar_genres(req.saved_track_ids, catalog)
    fav_artists = set(req.taste_artists)

    mitigations = []
    if genre_div:
        mitigations.append("Anti-repeat + genre variety — users report the same songs/artists looping")
    if mood_required:
        mitigations.append("Enforced mood match — users report recommendations ignoring mood")
    mitigations.append("Every track explains 'why' — users report low trust in recs")
    hit = rag.retrieve(req.moods, req.activities, req.free_text, k=1)
    if hit:
        mitigations.append(f"e.g. avoiding: \"{hit[0]['example_text'][:70]}…\"")

    # 1. candidates — real songs (iTunes) with mock fallback
    if music.source() == "itunes":
        cands = music.live_candidates(req.moods, req.activities, limit=48,
                                      seeds=req.taste_genres, artist_seeds=req.taste_artists)
        if len(cands) < n:
            cands = cat.candidates(catalog, req.moods, req.activities)
            note = "Live music source unavailable — using offline catalog."
        else:
            note = "Real songs via Apple Music."
    else:
        cands = cat.candidates(catalog, req.moods, req.activities)
    if mood_required:
        mm = [t for t in cands if set(req.moods) & set(t.moods)]
        cands = mm or cands

    # 2. anti-repeat: drop recently played + saved (the #1 complaint)
    block = set(req.recent_track_ids) | set(req.saved_track_ids)
    filtered = [t for t in cands if t.id not in block]
    avoided = len(cands) - len(filtered)
    if len(filtered) < n:
        filtered += [t for t in catalog if t.id not in block and t not in filtered]
        if filtered:
            note = "Widened beyond your mood to avoid repeats."

    # 3. split novel vs familiar, ranked (relevance + familiar-genre lean)
    filtered.sort(key=lambda t: _relevance(t, req, fam_genres, fav_artists), reverse=True)
    novel = [t for t in filtered if t.new_artist]
    familiar = [t for t in filtered if not t.new_artist]

    # 4. freshness blend
    novel_n = round(req.freshness / 100 * n)
    if req.freshness >= 100:
        note = note or "100% fresh — kept to your mood so it never feels random."
    if req.freshness <= 0:
        novel_n = max(novel_n, 1)
        note = note or "Mostly familiar, with one fresh pick so it isn't pure replay."
    novel_n = min(novel_n, len(novel))

    # 5. select with optional genre cap (genre variety vs repetition complaints)
    cap = max(2, -(-n // 3)) if genre_div else None
    used, gcount = set(), {}
    chosen = [(t, "fresh") for t in _pick(novel, novel_n, used, gcount, cap)]
    chosen += [(t, "familiar") for t in _pick(familiar, n - len(chosen), used, gcount, cap)]
    if len(chosen) < n:                       # backfill ignoring cap
        for t in _pick(filtered, n - len(chosen), used, gcount, None):
            chosen.append((t, "fresh" if t.new_artist else "familiar"))

    # 6. interleave fresh + familiar
    fresh = [c for c in chosen if c[1] == "fresh"]
    fam = [c for c in chosen if c[1] == "familiar"]
    ordered = []
    while fresh or fam:
        if fresh:
            ordered.append(fresh.pop(0))
        if fam:
            ordered.append(fam.pop(0))

    # 7. rationale (Claude batch if key, else rule-based)
    novel_ids = {t.id for t, tag in ordered if tag == "fresh"}
    llm = agent.llm_rationales([t for t, _ in ordered], req, novel_ids)
    items = [
        QueueItem(track=t, tag=tag,
                  why=(llm.get(t.id) if llm else None) or agent.rationale(t, req, tag == "fresh"))
        for t, tag in ordered
    ]
    applied = round(100 * sum(1 for _, tg in ordered if tg == "fresh") / max(len(ordered), 1))
    return Queue(items=items, freshness_applied=applied, avoided=avoided,
                 note=note, mitigations=mitigations)
