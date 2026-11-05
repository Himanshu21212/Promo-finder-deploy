"""Rules-only vs AI-assisted ranking on the same scripts.

    python -m promo_finder <scripts> -m gemini:gemini-3.8-flash --compare -o outputs_ai

Writes ai_vs_rules.md / ai_vs_rules.csv next to the normal outputs. Promos are matched by their
exact cut points; a promo the AI trimmed counts as a different cut.
"""
from __future__ import annotations

import csv
import io
import math

from .candidates import Promo
from .parser import fmt
from .pipeline import Result, run


def cut_key(p: Promo) -> tuple:
    return tuple((s.ep, round(s.start, 2), round(s.end, 2)) for s in p.segments)


def _cut_txt(p: Promo) -> str:
    return " + ".join(f"Ep {s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments)


def _spearman(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None

    def ranks(x):
        order = sorted(range(n), key=lambda i: x[i])
        r = [0.0] * n
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return round(cov / (va * vb), 2) if va and vb else None


def compare(episodes, title: str, judge, llm_top: int = 40, progress=None,
            n_single: int = 20, n_stitched: int = 6) -> tuple[Result, Result, dict]:
    rules = run(episodes, title, "rules", n_single, n_stitched, llm_top)
    ai = run(episodes, title, judge, n_single, n_stitched, llm_top, progress=progress)
    r_rank = {cut_key(p): p.rank for p in rules.promos}
    a_rank = {cut_key(p): p.rank for p in ai.promos}
    top_r = {k for k, v in r_rank.items() if v <= 10}
    top_a = {k for k, v in a_rank.items() if v <= 10}
    rated = [p for p in ai.candidates if p.llm and "overall" in p.llm]
    pairs = {
        "hook": ([p.scores["hook"] for p in rated], [p.llm["hook"] for p in rated]),
        "cliffhanger": ([p.scores["cliff"] for p in rated], [p.llm["cliffhanger"] for p in rated]),
        "new viewer": ([p.scores["standalone"] for p in rated], [p.llm["standalone"] for p in rated]),
        "overall": ([p.scores.get("rules_total", p.scores["total"]) for p in rated], [p.llm["overall"] for p in rated]),
    }
    disagree = sorted(rated, key=lambda p: -abs(p.scores.get("rules_total", 0) - p.scores.get("llm_total", 0)))[:6]
    summary = {
        "model": ai.model, "mock": ai.model == "mock", "ai_stats": ai.stats.get("ai", {}),
        "top10_overlap": len(top_r & top_a),
        "rank_correlation_shared": _spearman([r_rank[k] for k in r_rank if k in a_rank],
                                             [a_rank[k] for k in r_rank if k in a_rank]),
        "subscore_correlation": {k: _spearman(*v) for k, v in pairs.items()},
        "entered_top10": [p for p in ai.promos if p.rank <= 10 and cut_key(p) not in top_r],
        "left_top10": [p for p in rules.promos if p.rank <= 10 and cut_key(p) not in top_a],
        "biggest_disagreements": disagree,
        "rated": rated,
    }
    return rules, ai, summary


def to_markdown(rules: Result, ai: Result, s: dict) -> str:
    st = s["ai_stats"]
    head = ("# MOCK comparison: test only, NOT a real model\n\nThe 'AI' scores below come from a deterministic fake "
            "judge used to test the code path. Do not read anything into them.\n" if s["mock"] else
            f"# Rules only vs rules + AI judge ({ai.model})\n")
    out = [head,
           f"- Model calls: {st.get('calls', 0)} ({st.get('cached', 0)} from cache, {st.get('failed', 0)} failed); "
           f"candidates rated: {st.get('judged', 0)} of {st.get('shortlisted', 0)} shortlisted",
           f"- AI trims: {st.get('trims_applied', 0)} applied, {st.get('trims_rejected', 0)} rejected by the hard rules",
           f"- Top-10 overlap: **{s['top10_overlap']} of 10** promos are in both top-10 lists",
           f"- Rank correlation on promos both lists contain: {s['rank_correlation_shared']}",
           "- Rules vs model sub-score correlation (Spearman, on the rated shortlist): " +
           ", ".join(f"{k} {v}" for k, v in s["subscore_correlation"].items()), ""]
    if ai.stats.get("ai", {}).get("stopped"):
        out.append(f"> The AI judge {ai.stats['ai']['stopped']}. Remaining candidates kept their rules score.\n")
    out += ["## Top 10 side by side", "", "| # | Rules only | Rules + AI |", "|---|---|---|"]
    for i in range(10):
        a = rules.promos[i] if i < len(rules.promos) else None
        b = ai.promos[i] if i < len(ai.promos) else None
        cell = lambda p: f"{_cut_txt(p)} · {p.hook_beat.short(50).replace('|', '/')}" if p else ""  # noqa: E731
        out.append(f"| {i + 1} | {cell(a)} | {cell(b)} |")
    out += ["", "## Entered the top 10 with the AI judge", ""]
    out += [f"- #{p.rank} {_cut_txt(p)}: {p.hook_beat.short(70)} — model: {p.llm.get('why', '') if p.llm else ''}"
            for p in s["entered_top10"]] or ["- none"]
    out += ["", "## Left the top 10", ""]
    out += [f"- was #{p.rank} {_cut_txt(p)}: {p.hook_beat.short(70)}" for p in s["left_top10"]] or ["- none"]
    out += ["", "## Where rules and model disagree most", "",
            "| Cut | Rules score | Model score | Model's risk note |", "|---|---|---|---|"]
    for p in s["biggest_disagreements"]:
        out.append(f"| {_cut_txt(p)} | {100 * p.scores.get('rules_total', 0):.0f} | {100 * p.scores.get('llm_total', 0):.0f} | "
                   f"{(p.llm or {}).get('risk', '').replace('|', '/')} |")
    return "\n".join(out) + "\n"


def to_csv(s: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["cut", "kind", "rules_total", "llm_total", "blended_total", "rules_hook", "ai_hook", "rules_cliff",
                "ai_cliffhanger", "rules_new_viewer", "ai_standalone", "ai_overall", "trim", "why", "risk"])
    for p in sorted(s["rated"], key=lambda p: -p.scores["total"]):
        l = p.llm
        w.writerow([_cut_txt(p), p.kind, p.scores.get("rules_total"), p.scores.get("llm_total"), p.scores["total"],
                    p.scores["hook"], l["hook"], p.scores["cliff"], l["cliffhanger"], p.scores["standalone"],
                    l["standalone"], l["overall"], l.get("trim"), l.get("why"), l.get("risk")])
    return buf.getvalue()
