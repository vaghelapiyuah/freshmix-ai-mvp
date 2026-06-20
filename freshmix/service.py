"""Backend entrypoint — what an API (POST /v1/freshmix/generate) would call.

Ties intent parsing -> recommendation -> rationale into one call. Identical
requests are cached (Phase 8: viral-load) and returned as fresh copies so callers
can mutate the queue safely.
"""

from __future__ import annotations

from functools import lru_cache

from . import agent, recommend
from .schemas import Queue, QueueItem


@lru_cache(maxsize=256)
def _cached(free_text, moods_t, acts_t, freshness, recent_t, saved_t) -> Queue:
    req = agent.parse_intent(free_text, list(moods_t), list(acts_t), freshness,
                             list(recent_t), list(saved_t))
    return recommend.generate(req)


def generate_queue(free_text: str = "", moods=None, activities=None, freshness: int = 70,
                   recent=None, saved=None, catalog=None) -> Queue:
    if catalog is not None:                       # tests with a custom catalog bypass cache
        req = agent.parse_intent(free_text, moods or [], activities or [], freshness,
                                 recent or [], saved or [])
        return recommend.generate(req, catalog)
    q = _cached(free_text, tuple(moods or []), tuple(activities or []), freshness,
                tuple(recent or []), tuple(saved or []))
    return q.model_copy(deep=True)                # fresh copy — never hand out the cached object


def refresh_track(free_text: str = "", moods=None, activities=None, freshness: int = 70,
                  recent=None, saved=None, exclude=None, catalog=None) -> QueueItem | None:
    block = list(dict.fromkeys((recent or []) + (exclude or [])))
    q = generate_queue(free_text, moods, activities, freshness, block, saved, catalog)
    return q.items[0] if q.items else None
