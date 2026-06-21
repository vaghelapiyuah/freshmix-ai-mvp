"""FreshMix API client SDK (Phase 3).

Thin stdlib HTTP client mirroring the device SDK. Maps JSON <-> the same
contracts the in-process backend uses, so the frontend can swap transports
without changing call sites.
"""

from __future__ import annotations

import json
import urllib.request


class FreshMixClient:
    def __init__(self, base_url: str, timeout: int = 30):
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url      # Render fromService gives a bare host
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def health(self) -> dict:
        return self._get("/v1/health")

    def generate(self, free_text="", moods=None, activities=None, freshness=70,
                 recent=None, saved=None, taste_genres=None, taste_artists=None) -> dict:
        return self._post("/v1/freshmix/generate", {
            "free_text": free_text, "moods": moods or [], "activities": activities or [],
            "freshness": freshness, "recent_track_ids": recent or [],
            "saved_track_ids": saved or [], "taste_genres": taste_genres or [],
            "taste_artists": taste_artists or [],
        })

    def feedback(self, action, track_id, free_text="", moods=None, activities=None,
                 freshness=70, recent=None, saved=None, taste_genres=None,
                 taste_artists=None, exclude=None) -> dict:
        return self._post("/v1/freshmix/feedback", {
            "action": action, "track_id": track_id, "free_text": free_text,
            "moods": moods or [], "activities": activities or [], "freshness": freshness,
            "recent_track_ids": recent or [], "saved_track_ids": saved or [],
            "taste_genres": taste_genres or [], "taste_artists": taste_artists or [],
            "exclude": exclude or [],
        })
