"""Phase 0 — Foundation & evidence.

Pulls the real evidence behind FreshMix AI from the Review Discovery Engine
(the same data/code that powers the deployed app), freezes the design rules with
their numbers, and exports the review-insight corpus the agent/RAG layer uses.

Outputs (MVP/data/):
  - evidence.json          aggregate proof (frustrations, root causes, needs, segments)
  - design_rules.json      the 5 frozen rules, each with its evidence
  - review_insights.jsonl  one row per discovery pain point (the RAG corpus)

Run:  python phase0_evidence.py
Done when: review_insights.jsonl exists and 5 rules are written with evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Reuse the engine (sibling folder) — same data + analysis behind the live app.
ENGINE = Path(__file__).resolve().parent.parent / "Engine"
sys.path.insert(0, str(ENGINE))

from src.aggregation import build_dashboard          # noqa: E402
from src.analysis import RuleBasedAnalyzer            # noqa: E402
from src.cleaning import Cleaner                      # noqa: E402
from src.collectors import FileCollector              # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
APP_URL = "https://spotify-discovery-engine-cgdz6f8vcaxrmskv6gbtze.streamlit.app/"


def _load_reviews():
    files = ["data/spotify_live.json", "data/spotify_play.json"]
    raw = []
    for f in files:
        p = ENGINE / f
        if p.exists():
            raw += FileCollector(p).collect()
    if not raw:  # fallback to bundled sample
        raw = FileCollector(ENGINE / "data/sample_reviews.json").collect()
    return raw


def _pct(rows, key="pct_of_feedback", label="frustration", name=None):
    for r in rows:
        if name is None or r.get(label) == name:
            return r.get(key, 0.0)
    return 0.0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    DATA.mkdir(exist_ok=True)
    raw = _load_reviews()
    analyzed = RuleBasedAnalyzer().analyze(Cleaner.analyzable(Cleaner().clean(raw)))
    dash = build_dashboard(analyzed)
    discovery = [a for a in analyzed if not a.analysis.is_app_bug]

    # root-cause % helper
    rc = {r["key"]: r["pct"] for r in dash["root_causes"]}
    need = {r["unmet_need"]: r["pct_of_feedback"] for r in dash["unmet_needs"]}
    complaints = dash["top_discovery_complaints"]
    top_complaint = complaints[0] if complaints else {"frustration": "n/a", "pct_of_feedback": 0}
    p0 = dash["opportunity_scores"][0] if dash["opportunity_scores"] else {}

    evidence = {
        "source": APP_URL,
        "reviews_analyzed": dash["totals"]["analyzed_reviews"],
        "discovery_reviews": dash["totals"]["discovery_reviews"],
        "top_complaint": top_complaint,
        "p0_opportunity": p0,
        "root_causes_pct": rc,
        "unmet_needs_pct": need,
        "top_complaints": complaints,
    }
    (DATA / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    low_trust = rc.get("low_trust", 0)
    context = rc.get("context_mismatch", 0)
    fatigue = rc.get("recommendation_fatigue", 0)
    fresh_fam = need.get("fresh_but_familiar", 0)
    control = need.get("better_control", 0)

    design_rules = [
        {"rule": "Explain every track ('why this song')",
         "evidence": f"Low trust = {low_trust}% of root causes"},
        {"rule": "Take mood + activity + language as inputs",
         "evidence": f"Context mismatch = {context}% of root causes"},
        {"rule": "Give a Familiar↔Fresh slider (user controls freshness)",
         "evidence": f"'Better control' unmet need = {control}% of feedback"},
        {"rule": "Anti-repeat filter on recent/saved tracks",
         "evidence": f"Recommendation fatigue = {fatigue}%; #1 complaint = "
                     f"{top_complaint['frustration']} ({top_complaint['pct_of_feedback']}%)"},
        {"rule": "Generate fresh-but-familiar (not random) by default",
         "evidence": f"'Fresh-but-familiar' unmet need = {fresh_fam}% of feedback"},
    ]
    (DATA / "design_rules.json").write_text(json.dumps(design_rules, indent=2), encoding="utf-8")

    # Review-insight corpus: one row per discovery pain point.
    rows, seen = [], set()
    for a in discovery:
        an = a.analysis
        has_signal = (an.frustration.value != "none" or an.topic_cluster.value != "other"
                      or an.unmet_need.value != "none")
        if not has_signal:
            continue
        text = (an.normalized_summary or a.review.raw.text or "").strip()
        key = text.lower()[:80]
        if not text or key in seen:
            continue
        seen.add(key)
        rows.append({
            "theme": an.topic_cluster.value,
            "frustration": an.frustration.value,
            "unmet_need": an.unmet_need.value,
            "segment": an.segment.value,
            "severity": an.frustration_severity.value,
            "source": a.review.raw.source.value,
            "example_text": text[:240],
        })
    with (DATA / "review_insights.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- report ----
    line = "=" * 64
    print(f"\n{line}\nPHASE 0 — FOUNDATION & EVIDENCE\n{line}")
    print(f"Source: {APP_URL}")
    print(f"Reviews analyzed: {evidence['reviews_analyzed']} "
          f"({evidence['discovery_reviews']} discovery)")
    print(f"\n#1 frustration: {top_complaint['frustration']} "
          f"({top_complaint['pct_of_feedback']}%)   "
          f"P0 score: {p0.get('opportunity_score','-')}")
    print("Root causes:", ", ".join(f"{k} {v}%" for k, v in rc.items()))
    print("Unmet needs:", ", ".join(f"{k} {v}%" for k, v in need.items()))

    print("\nFrozen design rules:")
    for i, r in enumerate(design_rules, 1):
        print(f"  {i}. {r['rule']}\n     ← {r['evidence']}")

    print(f"\nCorpus rows written: {len(rows)}  ->  data/review_insights.jsonl")
    print("Also wrote: data/evidence.json, data/design_rules.json")

    ok = (DATA / "review_insights.jsonl").exists() and len(design_rules) == 5
    print(f"\nDONE-WHEN check: corpus exists & 5 rules written  ->  {'PASS' if ok else 'FAIL'}")
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
