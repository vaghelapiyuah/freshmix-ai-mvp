"""FreshMix AI MVP configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

MOODS = ["Focus", "Gym", "Chill", "Travel"]
ACTIVITIES = ["Work", "Commute", "Workout"]


@dataclass(frozen=True)
class Config:
    model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    queue_size: int = 8
    default_freshness: int = 70
    repeat_window: int = 50          # how many recent track ids count as "recently played"

    @property
    def has_api_key(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))


CONFIG = Config()
