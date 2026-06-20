"""Backend adapter — the single seam the frontend calls.

If FRESHMIX_API_URL is set, calls the HTTP API (Phase 3 split deploy); otherwise
runs the backend in-process. Same return types either way, so the frontend never
changes.
"""

from __future__ import annotations

import os

from . import service
from .client import FreshMixClient
from .schemas import Queue, QueueItem


def _url() -> str | None:
    return os.getenv("FRESHMIX_API_URL")


def mode() -> str:
    return f"API → {_url()}" if _url() else "in-process"


def generate(free_text="", moods=None, activities=None, freshness=70,
             recent=None, saved=None) -> Queue:
    url = _url()
    if url:
        data = FreshMixClient(url).generate(free_text, moods, activities, freshness,
                                            recent, saved)
        return Queue.model_validate(data)
    return service.generate_queue(free_text=free_text, moods=moods, activities=activities,
                                  freshness=freshness, recent=recent, saved=saved)


def refresh(free_text="", moods=None, activities=None, freshness=70,
            recent=None, saved=None, exclude=None) -> QueueItem | None:
    url = _url()
    if url:
        resp = FreshMixClient(url).feedback("refresh", track_id="", free_text=free_text,
                                            moods=moods, activities=activities,
                                            freshness=freshness, recent=recent,
                                            saved=saved, exclude=exclude)
        nxt = resp.get("next")
        return QueueItem.model_validate(nxt) if nxt else None
    return service.refresh_track(free_text=free_text, moods=moods, activities=activities,
                                 freshness=freshness, recent=recent, saved=saved,
                                 exclude=exclude)
