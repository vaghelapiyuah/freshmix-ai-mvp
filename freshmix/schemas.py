"""Pydantic contracts (the API boundary).

DiscoveryRequest -> generate_queue() -> Queue
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Track(BaseModel):
    id: str
    name: str
    artist: str
    genre: str
    year: int
    new_artist: bool                 # new-to-the-user / emerging
    moods: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    energy: float = 0.5              # 0..1
    valence: float = 0.5             # 0..1 (musical positivity)
    tempo: int = 110                 # BPM
    artwork_url: str | None = None   # album art (real source)
    preview_url: str | None = None   # 30s preview (real source)
    url: str | None = None           # link to the track


class DiscoveryRequest(BaseModel):
    free_text: str = ""
    moods: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    language: str = "en"
    freshness: int = 70              # 0 = familiar, 100 = fresh
    recent_track_ids: list[str] = Field(default_factory=list)
    saved_track_ids: list[str] = Field(default_factory=list)
    taste_genres: list[str] = Field(default_factory=list)    # from previously listened songs
    taste_artists: list[str] = Field(default_factory=list)   # favourite artists (history)
    taste_vector: dict = Field(default_factory=dict)         # audio-feature profile (history)


class QueueItem(BaseModel):
    track: Track
    why: str                         # "why this song" — trust
    tag: str                         # "fresh" | "familiar"


class Queue(BaseModel):
    items: list[QueueItem]
    freshness_applied: int
    avoided: int                     # how many recent/saved tracks were filtered out
    note: str = ""                   # guardrail / fallback note
    mitigations: list[str] = Field(default_factory=list)  # review pain points countered
