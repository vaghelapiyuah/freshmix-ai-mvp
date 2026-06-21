"""FreshMix AI — MVP frontend (Streamlit).

Mirrors the product wireframe: prompt, mood/activity chips, freshness slider,
Generate, and result cards with "why this song" + Save / Skip / Refresh.
Runs fully offline (mock catalog + rule-based agent); add ANTHROPIC_API_KEY for
the Claude rationale path.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from config import ACTIVITIES, CONFIG, MOODS
from freshmix import backend
from freshmix.feedback import UserState

DATA = Path(__file__).resolve().parent / "data"


def _load_evidence():
    """Phase 0 outputs — shown as inline proof for why the feature exists."""
    try:
        ev = json.loads((DATA / "evidence.json").read_text(encoding="utf-8"))
        rules = json.loads((DATA / "design_rules.json").read_text(encoding="utf-8"))
        return ev, rules
    except Exception:
        return None, None

st.set_page_config(page_title="FreshMix AI", page_icon="🎧", layout="centered")

st.markdown("""
<style>
.block-container{max-width:720px;padding-top:2.2rem}
.fm-head{display:flex;align-items:center;gap:14px;margin:0 0 2px}
.fm-logo{width:48px;height:48px;border-radius:14px;background:#1DB954;display:flex;
  align-items:center;justify-content:center;font-size:24px;color:#06381c}
.fm-title{font-size:30px;font-weight:700;color:#fff;letter-spacing:-0.5px}
.fm-label{font-size:12px;font-weight:700;letter-spacing:.12em;color:#8a8a8a;
  text-transform:uppercase;margin:16px 0 4px}
.fm-card{display:flex;gap:14px;background:#181818;border:1px solid #262626;
  border-radius:14px;padding:14px 16px;margin-bottom:8px}
.fm-art{width:54px;height:54px;border-radius:10px;flex:none;background:#202020;
  border:1px solid #2e2e2e;display:flex;align-items:center;justify-content:center;
  font-size:22px;color:#777}
.fm-art.fresh{background:rgba(29,185,84,.15);border-color:rgba(29,185,84,.4);color:#1DB954}
img.fm-art{object-fit:cover}
.fm-card a{color:#fff;text-decoration:none}
.fm-card a:hover{text-decoration:underline}
.fm-name{font-size:17px;font-weight:600;color:#fff}
.fm-artist{font-size:13px;color:#b3b3b3;margin-top:1px}
.fm-why{font-size:13px;color:#1DB954;background:rgba(29,185,84,.10);
  border-radius:8px;padding:4px 10px;display:inline-block;margin-top:8px}
.fm-tag{font-size:11px;font-weight:700;border-radius:10px;padding:2px 9px;margin-left:8px;
  vertical-align:middle}
.fm-fresh{background:rgba(29,185,84,.20);color:#1DB954}
.fm-fam{background:#2a2a2a;color:#b3b3b3}
.fm-saved{color:#1DB954;font-size:12px;margin-left:6px;font-weight:600}
.stButton>button{border-radius:10px}
</style>
""", unsafe_allow_html=True)

# --- state ---
if "user" not in st.session_state:
    st.session_state.user = UserState()
if "queue" not in st.session_state:
    st.session_state.queue = []
if "params" not in st.session_state:
    st.session_state.params = {}
user: UserState = st.session_state.user


def _params():
    return dict(
        free_text=st.session_state.get("prompt", ""),
        moods=st.session_state.get("moods", []),
        activities=st.session_state.get("acts", []),
        freshness=st.session_state.get("fresh", CONFIG.default_freshness),
    )


def _do_generate():
    p = _params()
    prev = st.session_state.get("queue") or []
    if prev and user.dissatisfied([it.track.id for it in prev]):
        user.freshness_bias = min(40, user.freshness_bias + 15)   # bump once per generate
    eff = max(0, p["freshness"] - user.freshness_bias)
    q = backend.generate(free_text=p["free_text"], moods=p["moods"],
                         activities=p["activities"], freshness=eff,
                         recent=user.block_ids(), saved=user.saved,
                         taste_genres=user.top_genres(3), taste_artists=user.top_artists(3))
    st.session_state.queue = q.items
    st.session_state.qmeta = q
    st.session_state.params = p
    for it in q.items:
        if it.track.id not in user.recent:
            user.recent.append(it.track.id)
        user.observe(it.track, 0.5)              # listening history (genre + artist)


def _replace(idx, mark_skip):
    q = st.session_state.queue
    if idx >= len(q):
        return
    tid = q[idx].track.id
    user.apply("skip" if mark_skip else "view", tid)
    if tid not in user.recent:
        user.recent.append(tid)
    shown = [it.track.id for it in q]
    pr = st.session_state.params
    repl = backend.refresh(free_text=pr["free_text"], moods=pr["moods"],
                           activities=pr["activities"], freshness=pr["freshness"],
                           recent=user.block_ids(), saved=user.saved,
                           taste_genres=user.top_genres(3),
                           taste_artists=user.top_artists(3), exclude=shown)
    if repl:
        q[idx] = repl
        user.recent.append(repl.track.id)
    else:
        q.pop(idx)


# --- header ---
st.markdown('<div class="fm-head"><div class="fm-logo">♫</div>'
            '<div class="fm-title">FreshMix AI</div></div>', unsafe_allow_html=True)
st.caption("Fresh-but-familiar discovery — mood, activity, and a freshness dial you control."
           + ("  ·  Claude rationale ON" if CONFIG.has_api_key else "  ·  offline mode")
           + f"  ·  backend: {backend.mode()}")

_ev, _rules = _load_evidence()
if _ev and _rules:
    with st.expander("Why this feature? (evidence from review analysis)"):
        tc = _ev.get("top_complaint", {})
        st.caption(f"From {_ev.get('reviews_analyzed', '?')} real Spotify reviews · "
                   f"#1 frustration: {tc.get('frustration', '?')} "
                   f"({tc.get('pct_of_feedback', '?')}%)")
        for r in _rules:
            st.markdown(f"- **{r['rule']}** — {r['evidence']}")

st.text_input("Prompt", key="prompt",
              placeholder="Refresh my playlist but keep the same vibe",
              label_visibility="collapsed")

st.markdown('<div class="fm-label">Mood</div>', unsafe_allow_html=True)
st.pills("Mood", MOODS, selection_mode="multi", key="moods", label_visibility="collapsed",
         default=["Focus"])
st.markdown('<div class="fm-label">Activity</div>', unsafe_allow_html=True)
st.pills("Activity", ACTIVITIES, selection_mode="multi", key="acts",
         label_visibility="collapsed", default=["Work"])

_cur = st.session_state.get("fresh", CONFIG.default_freshness)
st.markdown(f'<div class="fm-label">Freshness — '
            f'<span style="color:#1DB954">{_cur}% fresh</span></div>', unsafe_allow_html=True)
st.slider("Freshness", 0, 100, CONFIG.default_freshness, key="fresh",
          label_visibility="collapsed",
          help="0 = familiar favourites · 100 = all-new discovery")
valid = bool(st.session_state.get("prompt")) or bool(st.session_state.get("moods")) \
    or bool(st.session_state.get("acts"))
c1, c2 = st.columns([3, 1])
c1.caption("Familiar  ←————————————→  Fresh")
gen = c2.button("Generate FreshMix", type="primary", use_container_width=True,
                disabled=not valid)
if not valid:
    st.caption("Add a prompt or pick a mood / activity to generate.")
if gen:
    st.session_state.error = None
    try:
        with st.spinner("Generating your FreshMix…"):
            _do_generate()
    except Exception as e:                       # error state
        st.session_state.error = str(e)

# --- results / error / empty states ---
q = st.session_state.queue
if st.session_state.get("error"):
    st.error(f"Couldn't generate a mix: {st.session_state.error}")
    if st.button("Retry"):
        st.session_state.error = None
        try:
            with st.spinner("Retrying…"):
                _do_generate()
        except Exception as e:
            st.session_state.error = str(e)
        st.rerun()
elif q:
    meta = st.session_state.get("qmeta")
    if meta:
        msg = f"{meta.freshness_applied}% fresh · {meta.avoided} repeats filtered out"
        if meta.note:
            msg += f" · {meta.note}"
        st.caption(msg)
        if user.top_genres():
            st.caption("🎧 Tuned to your listening: " + ", ".join(user.top_genres(3)))
        if getattr(meta, "mitigations", None):
            with st.expander("Countering real review pain points (from the engine)"):
                for m in meta.mitigations:
                    st.markdown(f"- {m}")
    if user.dissatisfied([it.track.id for it in q]):
        st.info("Lots of skips — your next mix will lean more familiar.")

    for i, it in enumerate(list(q)):
        t = it.track
        saved = t.id in user.saved
        tagcls = "fm-fresh" if it.tag == "fresh" else "fm-fam"
        fresh = " fresh" if it.tag == "fresh" else ""
        art = (f'<img src="{t.artwork_url}" class="fm-art{fresh}">' if t.artwork_url
               else f'<div class="fm-art{fresh}">♪</div>')
        name = f'<a href="{t.url}" target="_blank">{t.name}</a>' if t.url else t.name
        saved_html = '<span class="fm-saved">✓ saved</span>' if saved else ""
        st.markdown(
            f'<div class="fm-card">{art}<div>'
            f'<div class="fm-name">{name}'
            f'<span class="fm-tag {tagcls}">{it.tag}</span>{saved_html}</div>'
            f'<div class="fm-artist">{t.artist} · {t.genre} · {t.year}</div>'
            f'<div class="fm-why">Why? {it.why}</div></div></div>',
            unsafe_allow_html=True)
        if t.preview_url:
            st.audio(t.preview_url, format="audio/mp4")
        b1, b2, b3 = st.columns(3)
        if b1.button("Save", key=f"s{i}_{t.id}", use_container_width=True):
            user.apply("save", t.id); user.observe(t, 2.0); st.rerun()
        if b2.button("Skip", key=f"k{i}_{t.id}", use_container_width=True):
            _replace(i, mark_skip=True); st.rerun()
        if b3.button("Refresh", key=f"r{i}_{t.id}", use_container_width=True):
            _replace(i, mark_skip=False); st.rerun()
else:
    st.info("Pick a mood + activity, set freshness, and tap **Generate FreshMix**.")
