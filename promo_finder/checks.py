"""Automatic quality checks: every promo is re-verified against the script after the run."""
from __future__ import annotations

import re

from .candidates import HOOK_WINDOW, MAX_LEN, MIN_LEN, _utterances
from .parser import fmt
from .pipeline import Result


def run_checks(r: Result) -> dict:
    eps = {e.num: e for e in r.episodes}
    promos = {p.id: p for p in r.promos + r.by_episode}.values()
    rows = []
    for p in promos:
        fails = []
        if not (MIN_LEN - 0.01 <= p.duration <= MAX_LEN + 0.01):
            fails.append(f"length {p.duration:.1f}s outside 20-60s")
        if p.hook_at > HOOK_WINDOW + 0.01:
            fails.append(f"hook lands at {p.hook_at:.1f}s (>3s)")
        for a, b in zip(p.segments, p.segments[1:]):
            if not (b.ep > a.ep or (b.ep == a.ep and b.start >= a.end)):
                fails.append("segments out of story order / overlapping")
        for s in p.segments:
            ep = eps[s.ep]
            lines = _utterances(ep)
            for t, what in ((s.start, "start"), (s.end, "end")):
                if any(l.start < t - 0.05 and l.end > t + 0.05 for l in lines):
                    fails.append(f"Ep {s.ep} {what} {fmt(t)} cuts inside a spoken line")
            starts = {round(b.start, 2) for b in ep.beats}
            ends = {round(b.end, 2) for b in ep.beats} | {round(ep.duration, 2)}
            if round(s.start, 2) not in starts or round(s.end, 2) not in ends:
                fails.append(f"Ep {s.ep} {fmt(s.start)}-{fmt(s.end)} is not a timestamp from the script")
        rows.append({"id": p.id, "pass": not fails, "fails": fails, "flags": p.flags})
    covered = {p.episodes[0] for p in r.by_episode}
    missing = sorted(set(eps) - covered)
    tiers = {"A": 0, "B": 0, "C": 0}
    for p in r.by_episode:
        t = p.scores["total"]
        tiers["A" if t >= 0.85 else "B" if t >= 0.75 else "C"] += 1
    flag_counts: dict[str, int] = {}
    for p in r.promos:
        for f in p.flags:
            key = re.sub(r"\s*\(Ep \d+\)", "", f.split(":")[0]).strip()
            flag_counts[key] = flag_counts.get(key, 0) + 1
    return {
        "checked": len(rows), "passed": sum(r_["pass"] for r_ in rows), "rows": rows,
        "episodes_with_a_promo": len(covered), "episodes_without": missing, "library_tiers": tiers,
        "ranked_flag_counts": dict(sorted(flag_counts.items(), key=lambda kv: -kv[1])),
        "ranked_episodes": len({e for p in r.promos for e in p.episodes}),
    }


def checks_markdown(c: dict) -> str:
    out = ["# Automatic quality checks", "",
           f"**{c['passed']} / {c['checked']} promos pass every hard rule** "
           "(20–60 s, hook inside 3 s, no cut inside a spoken line, segments in story order, "
           "every cut point is a real timestamp from the script).", "",
           f"- Episodes with at least one usable clip: **{c['episodes_with_a_promo']}** "
           f"(none found in: {', '.join(map(str, c['episodes_without'])) or '—'})",
           f"- Best-clip-per-episode tiers: A {c['library_tiers']['A']} · B {c['library_tiers']['B']} · "
           f"C {c['library_tiers']['C']} (C = probably not worth posting)",
           f"- Ranked list spans **{c['ranked_episodes']}** different episodes", "",
           "## Soft flags on the ranked list (things a human should eyeball)", ""]
    out += [f"- {k}: {v}" for k, v in c["ranked_flag_counts"].items()] or ["- none"]
    bad = [r for r in c["rows"] if not r["pass"]]
    out += ["", "## Hard-rule failures", ""]
    out += [f"- {r['id']}: {'; '.join(r['fails'])}" for r in bad] or ["- none"]
    return "\n".join(out) + "\n"
