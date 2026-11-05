"""Pick the best non-overlapping promos and decide which to post first."""
from __future__ import annotations

import re

from . import lexicon as L
from .candidates import Promo, season_pos
from .parser import Beat


def _overlap(a, b) -> float:
    if a.ep != b.ep:
        return 0.0
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    return inter / max(1e-6, min(a.dur, b.dur))


def _key_beats(p: Promo) -> set[tuple[int, int]]:
    return {(p.hook_beat.ep, p.hook_beat.idx), (p.cliff_beat.ep, p.cliff_beat.idx)}


def _all_beats(p: Promo) -> set[tuple[int, int]]:
    return {(b.ep, b.idx) for b in p.beats if b.kind != "camera"}


def select(cands: list[Promo], n: int, per_ep: int = 2, max_overlap: float = 0.3,
           caps: dict | None = None, taken: list[Promo] | None = None, key=None,
           no_shared_beats: bool = False) -> list[Promo]:
    """Greedy best-first pick with no heavy overlaps (also against `taken`), at most `per_ep`
    single clips per episode, and optional per-kind caps, e.g. {"stitched": 6}.
    no_shared_beats: also reject a promo whose hook or cliffhanger line already appears in a
    picked promo (or vice versa), so the same story beat is not posted twice."""
    key = key or (lambda p: p.scores["total"])
    picked: list[Promo] = []
    prior = list(taken or [])
    for p in sorted(cands, key=lambda p: -key(p)):
        if caps and sum(q.kind == p.kind for q in picked) >= caps.get(p.kind, n):
            continue
        if any(_overlap(s, t) > max_overlap for q in picked + prior for s in p.segments for t in q.segments):
            continue
        if p.kind == "single" and sum(q.kind == "single" and q.episodes == p.episodes for q in picked) >= per_ep:
            continue
        if no_shared_beats and any(_key_beats(p) & _all_beats(q) or _key_beats(q) & _all_beats(p)
                                   for q in picked + prior):
            continue
        picked.append(p)
        if len(picked) == n:
            break
    return picked


# ----------------------------------------------------------------- copy lines
def quote(b: Beat, n: int = 70) -> str:
    t = b.text.strip().strip('"').strip()
    if b.kind == "dialogue":
        t = t if len(t) <= n else t[: n - 1].rstrip() + "…"
        return f'“{t}”'
    clause = t.split(". ")[0].split("; ")[0]
    words = clause.split()
    clause = " ".join(words[:14]) + ("…" if len(words) > 14 else "")
    return f"[{clause[0].lower() + clause[1:] if clause else ''}]"


def lead_trope(p: Promo, premise: set[str]) -> str | None:
    w: dict[str, float] = {}
    for b in p.beats:
        for t in b.tropes:
            w[t] = w.get(t, 0) + L.TROPES[t][2] * (1.3 if t in premise else 1.0) * (0.5 + b.heat)
    return max(w, key=w.get) if w else None


def _hook_phrase(b: Beat) -> str:
    t = b.text.lower()
    if b.kind != "dialogue":
        for pat, name in [(r"slap", "a slap"), (r"riding crop|whip", "a whip strike"),
                          (r"punch|strike|struck", "a punch"), (r"explo|detonat|shatter", "an explosion"),
                          (r"fire|blaze|flame|inferno|rafters|beam", "fire"), (r"blood|thorn|briar", "blood"),
                          (r"one knee|kneel", "a stranger dropping to one knee"), (r"burst|fly open|kicked open", "a door bursting open")]:
            if re.search(pat, t):
                return name
        return "a shock image"
    q = b.text.strip().strip('"')
    return f"“{q}”" if len(q) <= 42 else "a hard line"


def _cliff_phrase(b: Beat) -> str:
    t = b.text.strip().strip('"')
    tl = t.lower()
    if re.search(r"accept my hand|marry me|be my wife", tl):
        return "the proposal, before she answers"
    if re.search(r"guards|arrest|seize|remove her|take her", tl):
        return "the order, before anyone moves"
    if re.search(r"is my son|the duke|i am the|you are the|rightful", tl):
        return "the reveal, before anyone reacts"
    if t.endswith("?"):
        return "a question nobody answers"
    if b.kind == "dialogue" and t.endswith(("...", "…", "—")):
        return "a sentence left hanging"
    if b.kind == "dialogue":
        return "a threat that hasn't landed yet"
    for pat, phrase in [
        (r"cliffhanger|sting|cut to black|silence", "the episode's own cliffhanger sting"),
        (r"inches|millimet|stops mere|stops just", "a threat frozen inches from landing"),
        (r"one knee|kneel|ring up", "the proposal, before she answers"),
        (r"burst|door|latch|appears|footsteps", "someone arriving"),
        (r"dangl|swing|pulls out|found|reveal", "the hidden thing coming to light"),
        (r"drag|seiz|arrest|shackle", "her being dragged away"),
        (r"tackl|dives|lunges? across", "a leap into danger"),
        (r"raises|lunge|aims|draws|jab", "a blow that hasn't landed"),
        (r"gasp|horror|terror|recoil|panic|stunned|freez|shock", "a frozen moment of shock"),
        (r"stares|glare|eyes burn|resolve|defian|head high|jaw", "a look that promises a fight"),
    ]:
        if re.search(pat, tl):
            return phrase
    return "an unresolved beat"


def why_line(p: Promo, premise: set[str]) -> str:
    lead = lead_trope(p, premise)
    pitch = L.TROPES[lead][1] if lead else "A confrontation that keeps escalating"
    cliff = _cliff_phrase(p.cliff_beat)
    if p.hook_beat.kind != "dialogue":   # a visual hook is worth naming; a spoken one is already quoted on the card
        return f"{pitch}. Opens on {_hook_phrase(p.hook_beat)}; cuts on {cliff}."
    return f"{pitch}. Cuts on {cliff}."


# ----------------------------------------------------------------- posting order
def post_order(promos: list[Promo], eps: dict, premise: set[str]) -> list[Promo]:
    """Greedy ordering: quality + funnel position, with a diversity penalty so the
    first week of posts doesn't repeat the same episode or trope."""
    for p in promos:
        early = 1 - season_pos(min(p.episodes), eps)
        p.scores["funnel"] = round(early, 3)
        p.scores["priority"] = round(p.scores["total"] + 0.15 * early, 4)
    remaining = promos[:]
    ordered: list[Promo] = []
    while remaining:
        def eff(p):
            pen = 0.0
            for q in ordered[-3:]:
                if set(p.episodes) & set(q.episodes):
                    pen += 0.04
                if p.tropes[:1] and p.tropes[:1] == q.tropes[:1]:
                    pen += 0.03
            return p.scores["priority"] - pen
        best = max(remaining, key=eff)
        ordered.append(best)
        remaining.remove(best)
    for i, p in enumerate(ordered, 1):
        p.rank = i
        p.id = f"P{i:02d}"
        p.post_reason = _reason(p, premise)
    return ordered


def _reason(p: Promo, premise: set[str]) -> str:
    """Why this promo sits where it does in the posting order, in plain sentences."""
    s = p.scores
    quality = []
    if s["hook"] >= 0.75:
        quality.append("a very strong hook")
    elif s["hook"] >= 0.55:
        quality.append("a solid hook")
    if s["cliff"] >= 0.75:
        quality.append("a hard cliffhanger")
    out = []
    if quality:
        q = " and ".join(quality)
        out.append(q[0].upper() + q[1:] + ".")
    if lead_trope(p, premise) in premise:
        out.append("It sells the show's premise.")
    if s["funnel"] >= 0.8:
        out.append(f"It's from Ep {min(p.episodes)}, so a new viewer who taps lands right where it cuts.")
    elif s["funnel"] < 0.4:
        out.append("It's a late-season payoff: post it after the premise promos have built an audience.")
    if s["standalone"] >= 0.9:
        out.append("Needs no backstory.")
    if p.kind == "stitched":
        out.append("Works as a mini trailer for the arc.")
    return " ".join(out[:5]) or "Balanced on every score."
