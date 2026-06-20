"""Feedback state — save / skip / refresh drive the learning loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserState:
    saved: list[str] = field(default_factory=list)       # saved track ids
    skipped: list[str] = field(default_factory=list)     # skipped track ids
    recent: list[str] = field(default_factory=list)      # recently served (anti-repeat)
    freshness_bias: int = 0                               # nudges next freshness

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
