"""Backend entrypoint — what an API (POST /v1/freshmix/generate) would call.

Ties intent parsing -> recommendation -> rationale into one call.
"""

from __future__ import annotations

from . import agent, recommend
from .schemas import Queue, QueueItem


def generate_queue(free_text: str = "", moods=None, activities=None, freshness: int = 70,
                   recent=None, saved=None, catalog=None) -> Queue:
    req = agent.parse_intent(
        free_text, moods or [], activities or [], freshness, recent or [], saved or [],
    )
    return recommend.generate(req, catalog)


def refresh_track(free_text: str = "", moods=None, activities=None, freshness: int = 70,
                  recent=None, saved=None, exclude=None, catalog=None) -> QueueItem | None:
    """Return one replacement track not already shown (the Refresh button)."""
    block = list(dict.fromkeys((recent or []) + (exclude or [])))
    q = generate_queue(free_text, moods, activities, freshness, block, saved, catalog)
    return q.items[0] if q.items else None
