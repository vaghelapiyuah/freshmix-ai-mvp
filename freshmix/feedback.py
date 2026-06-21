"""Feedback state — save / skip / refresh drive the learning loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserState:
    saved: list[str] = field(default_factory=list)       # saved track ids
    skipped: list[str] = field(default_factory=list)     # skipped track ids
    recent: list[str] = field(default_factory=list)      # recently served (anti-repeat)
    freshness_bias: int = 0                               # nudges next freshness
    taste: dict = field(default_factory=dict)            # genre -> weight (history)
    taste_artist: dict = field(default_factory=dict)     # artist -> weight (history)

    def learn(self, genre: str, weight: float = 1.0) -> None:
        if genre:
            self.taste[genre] = self.taste.get(genre, 0.0) + weight

    def learn_artist(self, artist: str, weight: float = 1.0) -> None:
        if artist:
            self.taste_artist[artist] = self.taste_artist.get(artist, 0.0) + weight

    def observe(self, track, weight: float = 0.5) -> None:
        """Update genre + artist taste from a listened/saved track."""
        self.learn(getattr(track, "genre", ""), weight)
        self.learn_artist(getattr(track, "artist", ""), weight)

    def top_genres(self, k: int = 3) -> list[str]:
        return [g for g, _ in sorted(self.taste.items(), key=lambda x: -x[1])[:k]]

    def top_artists(self, k: int = 3) -> list[str]:
        return [a for a, _ in sorted(self.taste_artist.items(), key=lambda x: -x[1])[:k]]

    def apply(self, action: str, track_id: str) -> None:
        if track_id not in self.recent:
            self.recent.append(track_id)
        if action == "save" and track_id not in self.saved:
            self.saved.append(track_id)
        elif action == "skip" and track_id not in self.skipped:
            self.skipped.append(track_id)

    def block_ids(self) -> list[str]:
        return list(dict.fromkeys(self.recent + self.saved + self.skipped))

    def dissatisfied(self, last_queue_ids: list[str]) -> bool:
        """Skipped most of the last queue → bias toward familiar next time."""
        if not last_queue_ids:
            return False
        skipped_in = sum(1 for i in last_queue_ids if i in self.skipped)
        return skipped_in >= max(2, len(last_queue_ids) * 0.6)
