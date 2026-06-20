"""Context service — infer the user's taste from their saved tracks.

In production this calls the Spotify API (recent plays, saved, top artists) to
build a taste vector. Offline, it derives familiar genres from saved track ids
against the mock catalog.
"""

from __future__ import annotations

from .schemas import Track


def familiar_genres(saved_ids: list[str], catalog: list[Track]) -> set[str]:
    by_id = {t.id: t for t in catalog}
    return {by_id[i].genre for i in saved_ids if i in by_id}
