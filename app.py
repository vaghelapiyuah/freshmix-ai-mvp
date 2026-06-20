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
.block-container{max-width:760px}
.fm-head{display:flex;align-items:center;gap:12px;margin:4px 0 2px}
.fm-logo{width:46px;height:46px;border-radius:12px;background:#1DB954}
.fm-title{font-size:30px;font-weight:700;color:#fff}
.fm-card{background:#181818;border:1px solid #262626;border-radius:14px;padding:14px 16px;margin-bottom:6px}
.fm-name{font-size:18px;font-weight:600;color:#fff}
.fm-artist{font-size:14px;color:#b3b3b3}
.fm-why{font-size:14px;color:#1DB954;background:rgba(29,185,84,.10);
  border-radius:8px;padding:4px 10px;display:inline-block;margin-top:6px}
.fm-tag{font-size:12px;font-weight:700;border-radius:10px;padding:2px 10px;margin-left:8px}
.fm-fresh{background:rgba(29,185,84,.18);color:#1DB954}
.fm-fam{background:#2a2a2a;color:#b3b3b3}
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
    eff = max(0, p["freshness"] - user.freshness_bias)
    q = backend.generate(free_text=p["free_text"], moods=p["moods"],
                         activities=p["activities"], freshness=eff,
                         recent=user.block_ids(), saved=user.saved)
    st.session_state.queue = q.items
    st.session_state.qmeta = q
    st.session_state.params = p
    for it in q.items:
        if it.track.id not in user.recent:
            user.recent.append(it.track.id)


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
                           recent=user.block_ids(), saved=user.saved, exclude=shown)
    if repl:
        q[idx] = repl
        user.recent.append(repl.track.id)
    else:
        q.pop(idx)


# --- header ---
st.markdown('<div class="fm-head"><div class="fm-logo"></div>'
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

st.markdown("**Mood**")
st.pills("Mood", MOODS, selection_mode="multi", key="moods", label_visibility="collapsed",
         default=["Focus"])
st.markdown("**Activity**")
st.pills("Activity", ACTIVITIES, selection_mode="multi", key="acts",
         label_visibility="collapsed", default=["Work"])

st.markdown("**Freshness**")
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
        if getattr(meta, "mitigations", None):
            with st.expander("Countering real review pain points (from the engine)"):
                for m in meta.mitigations:
                    st.markdown(f"- {m}")
    if user.dissatisfied([it.track.id for it in q]):
        st.info("Lots of skips — nudging the next mix more familiar.")
        user.freshness_bias = min(40, user.freshness_bias + 15)

    for i, it in enumerate(list(q)):
        t = it.track
        saved = t.id in user.saved
        tagcls = "fm-fresh" if it.tag == "fresh" else "fm-fam"
        st.markdown(
            f'<div class="fm-card"><div class="fm-name">{t.name}'
            f'<span class="fm-tag {tagcls}">{it.tag}</span>'
            f'{" ✓ saved" if saved else ""}</div>'
            f'<div class="fm-artist">{t.artist} · {t.genre} · {t.year}</div>'
            f'<div class="fm-why">Why? {it.why}</div></div>',
            unsafe_allow_html=True)
        b1, b2, b3 = st.columns(3)
        if b1.button("Save", key=f"s{i}_{t.id}", use_container_width=True):
            user.apply("save", t.id); st.rerun()
        if b2.button("Skip", key=f"k{i}_{t.id}", use_container_width=True):
            _replace(i, mark_skip=True); st.rerun()
        if b3.button("Refresh", key=f"r{i}_{t.id}", use_container_width=True):
            _replace(i, mark_skip=False); st.rerun()
else:
    st.info("Pick a mood + activity, set freshness, and tap **Generate FreshMix**.")
