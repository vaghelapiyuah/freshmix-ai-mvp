"""Mock music catalog (offline candidate source).

Stands in for the Spotify catalog so the MVP runs with no API keys. A real build
swaps `load_catalog()` / `candidates()` for Spotify recommendations seeded by the
user's taste vector — the rest of the pipeline is unchanged.
"""

from __future__ import annotations

from .schemas import Track

# genre -> (moods, activities, base energy/valence/tempo)
_GENRE = {
    "Lo-fi":      (["Focus", "Chill"], ["Work", "Commute"], 0.30, 0.55, 82),
    "Ambient":    (["Focus", "Chill"], ["Work"],            0.20, 0.45, 70),
    "Electronic": (["Gym", "Travel"],  ["Workout", "Commute"], 0.85, 0.65, 128),
    "Hip-hop":    (["Gym", "Travel"],  ["Workout", "Commute"], 0.80, 0.60, 95),
    "Indie":      (["Chill", "Travel"], ["Commute", "Work"], 0.55, 0.60, 112),
    "Pop":        (["Travel", "Gym"],  ["Commute", "Workout"], 0.70, 0.75, 118),
    "R&B":        (["Chill", "Travel"], ["Work", "Commute"], 0.50, 0.55, 100),
    "Rock":       (["Gym"],            ["Workout"],          0.88, 0.55, 140),
}
_ADJ = ["Neon", "Velvet", "Midnight", "Golden", "Paper", "Electric", "Quiet",
        "Crimson", "Hollow", "Bright", "Slow", "Wild"]
_NOUN = ["Tide", "Echo", "Skyline", "Pulse", "Garden", "Static", "Mirror",
         "Horizon", "Ember", "Signal", "Drift", "Bloom"]


def load_catalog() -> list[Track]:
    tracks: list[Track] = []
    n = 0
    for genre, (moods, acts, en, val, tempo) in _GENRE.items():
        for i in range(6):
            new = i % 2 == 0  # half emerging artists
            adj = _ADJ[n % len(_ADJ)]
            noun = _NOUN[(n // 2) % len(_NOUN)]
            tracks.append(Track(
                id=f"t{n:03d}",
                name=f"{adj} {noun}",
                artist=("Emerging — " if new else "") + f"{genre} Artist {i + 1}",
                genre=genre,
                year=2024 if new else 2019,
                new_artist=new,
                moods=moods,
                activities=acts,
                energy=round(min(1.0, en + (i - 3) * 0.03), 2),
                valence=round(min(1.0, val + (i - 3) * 0.02), 2),
                tempo=tempo + (i - 3) * 3,
            ))
            n += 1
    return tracks


def candidates(catalog: list[Track], moods: list[str], activities: list[str]) -> list[Track]:
    """Filter by selected mood/activity tags; empty selection = whole catalog."""
    if not moods and not activities:
        return list(catalog)
    out = []
    for t in catalog:
        if (moods and set(moods) & set(t.moods)) or (activities and set(activities) & set(t.activities)):
            out.append(t)
    return out or list(catalog)
