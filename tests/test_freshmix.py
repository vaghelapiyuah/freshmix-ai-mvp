"""Offline tests — no API keys, no network.

Run:  pytest    or    python tests/test_freshmix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os  # noqa: E402
os.environ["MUSIC_SOURCE"] = "mock"      # deterministic, offline (no network in CI)

from config import CONFIG  # noqa: E402
from freshmix import generate_queue, refresh_track  # noqa: E402
from freshmix.agent import parse_intent, rationale  # noqa: E402
from freshmix.catalog import load_catalog  # noqa: E402


def test_parse_intent_reads_freshness_and_mood():
    req = parse_intent("Refresh my gym playlist with 60% new songs", [], [], 70, [], [])
    assert req.freshness == 60
    assert "Gym" in req.moods
    print("  [ok] parse_intent reads freshness % and mood from prompt")


def test_generate_blend_and_size():
    q = generate_queue(moods=["Focus"], activities=["Work"], freshness=70)
    assert len(q.items) == CONFIG.queue_size
    fresh = sum(1 for it in q.items if it.tag == "fresh")
    assert fresh >= CONFIG.queue_size * 0.5, "≈70% freshness should be majority-fresh"
    assert all(it.why for it in q.items), "every track needs a 'why'"
    print(f"  [ok] queue size {len(q.items)}, {q.freshness_applied}% fresh, all have rationale")


def test_anti_repeat_excludes_recent_and_saved():
    base = generate_queue(moods=["Gym"], activities=["Workout"], freshness=80)
    block = [base.items[0].track.id, base.items[1].track.id]
    q = generate_queue(moods=["Gym"], activities=["Workout"], freshness=80,
                       recent=block[:1], saved=block[1:])
    ids = {it.track.id for it in q.items}
    assert not (set(block) & ids), "recent/saved tracks must not reappear"
    print("  [ok] anti-repeat filter excludes recent + saved")


def test_freshness_extremes():
    q0 = generate_queue(moods=["Chill"], freshness=0)
    q100 = generate_queue(moods=["Chill"], freshness=100)
    assert any(it.tag == "fresh" for it in q0.items), "freshness 0 still injects ≥1 discovery"
    assert all(it.tag == "fresh" for it in q100.items), "freshness 100 is all-fresh"
    print("  [ok] freshness 0 injects discovery; 100 is all fresh")


def test_refresh_returns_new_track():
    q = generate_queue(moods=["Travel"], activities=["Commute"], freshness=60)
    shown = [it.track.id for it in q.items]
    repl = refresh_track(moods=["Travel"], activities=["Commute"], freshness=60,
                         recent=shown, exclude=shown)
    assert repl is not None and repl.track.id not in shown
    print("  [ok] refresh returns a track not already shown")


def test_rationale_nonempty():
    t = load_catalog()[0]
    from freshmix.schemas import DiscoveryRequest
    assert rationale(t, DiscoveryRequest(moods=["Focus"]), novel=True)
    print("  [ok] rationale is non-empty")


def test_rag_signals_and_mitigations():
    from freshmix import rag
    sig = rag.avoid_signals()
    assert set(sig) >= {"repetition", "mood", "explain", "n"}
    assert 0.0 <= sig["repetition"] <= 1.0
    q = generate_queue(moods=["Focus"], activities=["Work"], freshness=70)
    assert q.mitigations and any("why" in m.lower() for m in q.mitigations)
    print(f"  [ok] rag signals (corpus n={sig['n']}, rep={sig['repetition']}); "
          f"{len(q.mitigations)} mitigations surfaced")


def test_genre_variety_when_repetition_pain():
    from freshmix import rag
    sig = rag.avoid_signals()
    q = generate_queue(moods=["Focus", "Chill"], activities=["Work"], freshness=70)
    if sig["repetition"] >= 0.20:               # genre cap should be active
        cap = max(2, -(-CONFIG.queue_size // 3))
        from collections import Counter
        counts = Counter(it.track.genre for it in q.items)
        assert max(counts.values()) <= cap, f"genre cap {cap} exceeded: {counts}"
        print(f"  [ok] genre variety enforced (no genre > {cap})")
    else:
        print("  [ok] repetition pain below threshold; genre cap not required")


def test_skill_package_loads():
    from freshmix import skill
    s = skill.load()
    assert s.name == "freshmix-discovery"
    assert s.version.count(".") == 2 and s.version != "0.0.0"   # real semver, not fallback
    assert "fresh" in s.system.lower() and len(s.system) > 200
    assert len(s.tools) == 4 and "retrieve_review_insights" in s.tool_names
    assert "input" in s.schema and "output" in s.schema
    m = skill.manifest()
    assert m["corpus_rows"] > 0
    print(f"  [ok] skill '{s.name}' v{s.version}: {len(s.tools)} tools, "
          f"{m['corpus_rows']} grounding rows")


def test_agent_uses_packaged_skill():
    from freshmix import agent, skill
    assert agent.FRESHMIX_SKILL == skill.load().system   # not the inline fallback
    assert agent.SKILL_VERSION == "1.0.0"
    print("  [ok] agent runs from the packaged, versioned skill")


def test_agent_validate_and_fallback():
    from freshmix import agent
    ok, msg = agent.validate()
    # No key in the test env -> not active, and parse falls back to rule-based.
    if not CONFIG.has_api_key:
        assert ok is False
    req = agent.parse_intent("gym playlist with 40% new songs", [], [], 70, [], [])
    assert req.freshness == 40 and "Gym" in req.moods   # rule-based fallback works
    print(f"  [ok] agent.validate -> {ok} ({msg[:30]}…); rule-based fallback parses")


def test_agent_llm_parse_mocked():
    """Verify the Claude code path with a fake client (no key needed)."""
    from freshmix import agent
    from freshmix.agent import ParsedIntent

    class _Msgs:
        def parse(self, **kw):
            return type("R", (), {"parsed_output": ParsedIntent(
                moods=["Gym"], activities=["Workout"], freshness=55, language="en")})()

    class _Fake:
        messages = _Msgs()

    pi = agent._llm_parse("songs for the gym, mostly new", client=_Fake())
    assert pi and pi.freshness == 55 and "Gym" in pi.moods
    print("  [ok] Claude intent-parse path maps structured output (mocked)")


def test_api_contract():
    from fastapi.testclient import TestClient
    from api import app
    c = TestClient(app)
    assert c.get("/v1/health").json()["status"] == "ok"
    r = c.post("/v1/freshmix/generate",
               json={"moods": ["Focus"], "activities": ["Work"], "freshness": 70})
    assert r.status_code == 200
    q = r.json()
    assert len(q["items"]) == CONFIG.queue_size and q["items"][0]["why"]
    shown = [it["track"]["id"] for it in q["items"]]
    fb = c.post("/v1/freshmix/feedback",
                json={"action": "refresh", "track_id": shown[0], "moods": ["Focus"],
                      "freshness": 70, "exclude": shown}).json()
    assert fb["ok"] and fb["next"] and fb["next"]["track"]["id"] not in shown
    print("  [ok] API /v1 generate + feedback contract holds")


def test_feedback_loop_updates_state():
    from freshmix.feedback import UserState
    u = UserState()
    u.apply("save", "t1"); u.apply("skip", "t2"); u.apply("skip", "t3")
    assert "t1" in u.saved and "t2" in u.skipped and "t3" in u.skipped
    assert set(u.block_ids()) == {"t1", "t2", "t3"}            # recent+saved+skipped, deduped
    assert u.dissatisfied(["t2", "t3", "t4"]) is True          # 2/3 skipped -> bias familiar
    assert u.dissatisfied(["t4", "t5"]) is False
    print("  [ok] feedback loop updates state + detects skip-all dissatisfaction")


def test_rag_retrieve_relevance():
    from freshmix import rag
    hits = rag.retrieve(moods=["Chill"], activities=["Work"],
                        free_text="playlist feels repetitive", k=3)
    assert len(hits) <= 3
    if rag.load_corpus():
        assert hits and "example_text" in hits[0]
    print(f"  [ok] rag.retrieve returned {len(hits)} relevant pain points")


def test_frontend_states():
    import os
    os.environ.pop("FRESHMIX_API_URL", None)                   # use in-process backend
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert len([b for b in at.button if b.label == "Save"]) == 0    # empty state
    gen = [b for b in at.button if "Generate" in (b.label or "")]
    gen[0].click(); at.run()
    assert not at.exception
    assert len([b for b in at.button if b.label == "Save"]) == CONFIG.queue_size  # results
    print("  [ok] frontend empty -> results states render with no exceptions")


def test_edge_empty_inputs():
    q = generate_queue()                                   # no prompt, no chips
    assert len(q.items) == CONFIG.queue_size
    print("  [ok] edge: empty inputs still return a full queue")


def test_edge_no_candidates_widen():
    from freshmix.catalog import candidates, load_catalog
    cat = load_catalog()
    chill_ids = [t.id for t in candidates(cat, ["Chill"], [])]
    q = generate_queue(moods=["Chill"], freshness=70, recent=chill_ids)
    assert len(q.items) == CONFIG.queue_size               # widened beyond mood
    print("  [ok] edge: anti-repeat empties pool -> widened to fill queue")


def test_edge_language_fallback():
    from freshmix.agent import parse_intent
    req = parse_intent("give me songs in klingon", [], [], 70, [], [])
    assert req.language == "en"
    print("  [ok] edge: unsupported language falls back to en")


def test_edge_redact_pii():
    from freshmix.safety import redact_pii
    out = redact_pii("email me a@b.com or call 555-123-4567 please")
    assert "a@b.com" not in out and "555-123-4567" not in out and "[email]" in out
    print("  [ok] edge: email/phone redacted before agent + logs")


def test_edge_agent_malformed_fallback():
    from freshmix import agent

    class _Bad:
        class messages:
            @staticmethod
            def parse(**kw):
                raise RuntimeError("malformed agent output")

    assert agent._llm_parse("gym songs", client=_Bad) is None   # -> rule-based fallback
    print("  [ok] edge: malformed/raising agent response -> graceful fallback")


def test_edge_response_cache():
    from freshmix import service
    service._cached.cache_clear()
    a = generate_queue(moods=["Focus"], activities=["Work"], freshness=70)
    b = generate_queue(moods=["Focus"], activities=["Work"], freshness=70)
    assert service._cached.cache_info().hits >= 1               # identical request cached
    assert [i.track.id for i in a.items] == [i.track.id for i in b.items]
    a.items.pop()                                              # mutate one copy
    assert len(b.items) == CONFIG.queue_size                   # copies are independent
    print("  [ok] edge: identical requests cached; returned copies independent")


def test_edge_stale_corpus_graceful():
    import pathlib
    from freshmix import rag, recommend
    from freshmix.schemas import DiscoveryRequest
    orig = rag._CORPUS
    try:
        rag._CORPUS = pathlib.Path("does_not_exist.jsonl")
        rag.load_corpus.cache_clear()
        assert rag.avoid_signals()["n"] == 0
        q = recommend.generate(DiscoveryRequest(moods=["Focus"], freshness=70))
        assert len(q.items) == CONFIG.queue_size               # still works with no corpus
    finally:
        rag._CORPUS = orig
        rag.load_corpus.cache_clear()
    print("  [ok] edge: missing/stale corpus degrades gracefully")


def test_music_live_mapping():
    from freshmix import music
    fake = [{"trackId": 1, "trackName": "Real Song", "artistName": "Real Artist",
             "primaryGenreName": "Indie", "releaseDate": "2026-01-01",
             "artworkUrl100": "https://x/100x100bb.jpg",
             "previewUrl": "https://x/p.m4a", "trackViewUrl": "https://music.apple.com/x"}]
    orig = music._search
    try:
        music._search = lambda term, limit=12, country="us": tuple(fake)
        tracks = music.live_candidates(["Focus"], ["Work"], limit=5)
        t = tracks[0]
        assert t.name == "Real Song" and t.artist == "Real Artist"
        assert t.artwork_url and t.preview_url and t.url and t.new_artist
        assert "300x300" in t.artwork_url            # upscaled art
    finally:
        music._search = orig
    print("  [ok] live music mapping -> Track with real art/preview/link")


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    print(f"Running {len(tests)} FreshMix tests...\n")
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1; print(f"  [FAIL] {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1; print(f"  [ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
