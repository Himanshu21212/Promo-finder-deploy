"""Turn scored beats into promo candidates (single clips and stitched multi-moment promos).

Rules enforced in code, never left to a model:
  * every promo is 20-60 s long
  * the hook beat starts within the first 3 s
  * cuts land on shot boundaries and never in the middle of a spoken line
  * stitched segments play in story order and never overlap
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import lexicon as L
from .parser import Beat, Episode, fmt
from .scoring import _rx

MIN_LEN, MAX_LEN, HOOK_WINDOW = 20.0, 60.0, 3.0
PRE_ROLL = 2.5      # max seconds of picture allowed before the hook beat
POST_ROLL = 2.0     # max seconds of reaction allowed after the cliff beat


@dataclass
class Segment:
    ep: int
    start: float
    end: float
    beats: list[Beat] = field(default_factory=list)

    @property
    def dur(self) -> float:
        return self.end - self.start

    def stamp(self) -> str:
        return f"Ep {self.ep}  {fmt(self.start)} → {fmt(self.end)}"


@dataclass
class Promo:
    kind: str                         # "single" | "stitched"
    segments: list[Segment]
    hook_beat: Beat
    cliff_beat: Beat
    scores: dict = field(default_factory=dict)
    tropes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    why: str = ""
    id: str = ""
    rank: int = 0
    post_reason: str = ""
    llm: dict | None = None

    @property
    def duration(self) -> float:
        return round(sum(s.dur for s in self.segments), 2)

    @property
    def episodes(self) -> list[int]:
        return sorted({s.ep for s in self.segments})

    @property
    def beats(self) -> list[Beat]:
        return [b for s in self.segments for b in s.beats]

    @property
    def hook_at(self) -> float:
        s0 = self.segments[0]
        return round(max(0.0, self.hook_beat.start - s0.start), 2)


# ----------------------------------------------------------------- cut points
def _utterances(ep: Episode) -> list[Beat]:
    """Spoken lines, with split lines ("I said..." / "...let her go.") merged so we never cut between them."""
    lines = ep.lines
    out = list(lines)
    for a, b in zip(lines, lines[1:]):
        if a.text.rstrip('" ').endswith(("...", "…", "—")) and b.text.lstrip('" ').startswith(("...", "…")) \
                and b.start - a.end < 3.0:
            out.append(Beat(ep.num, -1, "dialogue", a.start, b.end, a.text + " " + b.text, a.speaker))
    return out


def _clean(t: float, lines: list[Beat]) -> bool:
    """True if t does not fall inside a spoken line (or between two halves of one)."""
    return not any(l.start < t - 0.05 and l.end > t + 0.05 for l in lines)


def cut_points(ep: Episode) -> tuple[list[float], list[float]]:
    lines = _utterances(ep)
    starts = sorted({round(b.start, 2) for b in ep.beats if b.kind in ("camera", "dialogue", "action")
                     and not (b.kind == "dialogue" and b.text.lstrip('" ').startswith(("...", "…")))})
    ends = sorted({round(b.end, 2) for b in ep.beats if b.kind in ("camera", "dialogue", "action")} | {round(ep.duration, 2)})
    return [t for t in starts if _clean(t, lines)], [t for t in ends if _clean(t, lines)]


def _start_for(anchor: Beat, starts: list[float]) -> float | None:
    ok = [t for t in starts if anchor.start - PRE_ROLL <= t <= anchor.start + 0.01]
    return max(ok) if ok else None


def _end_for(anchor: Beat, ends: list[float]) -> float | None:
    ok = [t for t in ends if anchor.end - 0.01 <= t <= anchor.end + POST_ROLL]
    return min(ok) if ok else None


def _inside(ep: Episode, s: float, e: float) -> list[Beat]:
    return [b for b in ep.beats if b.start >= s - 0.01 and b.end <= e + 0.05]


# ----------------------------------------------------------------- scoring a span
def hook_strength(b: Beat, s: float) -> float:
    """A hook must *land* inside 3 s: a long line or a late start is worth less."""
    land = (b.start - s) + ((b.end - b.start) if b.kind == "dialogue" else min(b.end - b.start, 1.0))
    return b.hook * (1.0 if land <= HOOK_WINDOW + 0.5 else 0.85 if land <= 5.5 else 0.7)


def _hook_of(beats: list[Beat], s: float) -> Beat | None:
    early = [b for b in beats if b.start - s <= HOOK_WINDOW and b.kind != "camera"]
    early = early or [b for b in beats if b.start - s <= HOOK_WINDOW]
    return max(early, key=lambda b: hook_strength(b, s), default=None)


def _cliff_of(beats: list[Beat], e: float) -> Beat | None:
    late = [b for b in beats if e - b.end <= 4.0]
    if not late:
        return None
    best = max(late, key=lambda b: (b.cliff, b.kind != "camera", b.end))
    # the 'cliffhanger text' should be a line or action, not a camera note, when one is close
    if best.kind == "camera":
        alt = [b for b in late if b.kind != "camera" and b.cliff >= best.cliff - 0.25]
        if alt:
            best = max(alt, key=lambda b: (b.cliff, b.end))
    return best


def body_score(beats: list[Beat], s: float, e: float) -> tuple[float, float]:
    """(body quality, longest sag in seconds)."""
    core = [b for b in beats if b.kind in ("dialogue", "action", "sfx")]
    if not core:
        return 0.0, e - s
    heats = [b.heat for b in core]
    mean = sum(heats) / len(heats)
    peak = max(heats)
    hot = sorted(b.start for b in core if b.heat >= 0.4)
    marks = [s] + hot + [e]
    sag = max(b - a for a, b in zip(marks, marks[1:]))
    q = 0.5 * min(1.0, mean / 0.55) + 0.3 * peak + 0.2 * (1 - min(sag, 20) / 20)
    return round(q, 3), round(sag, 1)


def standalone_score(beats: list[Beat], names: set[str], n_scene_jumps: int = 0) -> tuple[float, list[str]]:
    lines = [b for b in beats if b.kind == "dialogue"]
    flags = []
    debt = 0.0
    if lines:
        debt += 0.45 * lines[0].context
        if lines[0].context >= 0.5:
            flags.append("Opens mid-conversation")
        debt += min(0.3, 0.1 * sum(b.context > 0 for b in lines[1:]))
    speakers = " ".join(b.speaker.title() for b in lines)
    said = " ".join(b.text for b in lines)
    unknown = sorted({n for n in names if re.search(rf"\b{re.escape(n)}\b", said) and n not in speakers})
    if unknown:
        debt += min(0.35, 0.12 * len(unknown))
        flags.append("Mentions people a new viewer hasn't met: " + ", ".join(unknown[:4]))
    objs = sorted({m.group(0).lower() for b in lines for m in _rx(L.CONTEXT_NOUNS).finditer(b.text)})
    if objs:
        debt += min(0.12, 0.06 * len(objs))
        flags.append("Mentions things that need setup: " + ", ".join(objs[:3]))
    if n_scene_jumps:
        debt += 0.12 * n_scene_jumps
        flags.append(f"Jumps across {n_scene_jumps + 1} scenes")
    if len({b.speaker for b in lines}) > 4:
        debt += 0.1
        flags.append("Many speakers to follow")
    clarity = 0.15 if any(b.tropes for b in beats) else 0.0
    return round(max(0.0, min(1.0, 1.0 - debt + clarity)), 3), flags


def fit_score(d: float) -> float:
    if d < MIN_LEN or d > MAX_LEN:
        return 0.0
    if d < 25:
        return 0.75 + 0.15 * (d - 20) / 5
    if d <= 45:
        return 1.0
    return 1.0 - 0.3 * (d - 45) / 15


def _tropes(beats: list[Beat]) -> list[str]:
    counts: dict[str, int] = {}
    for b in beats:
        for t in b.tropes:
            counts[t] = counts.get(t, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


WEIGHTS = dict(hook=0.28, cliff=0.24, body=0.20, standalone=0.16, fit=0.06, premise=0.06)


def _total(sc: dict) -> float:
    return round(sum(WEIGHTS[k] * sc[k] for k in WEIGHTS), 4)


def season_pos(ep_num: int, eps: dict[int, Episode]) -> float:
    """0.0 = first loaded episode, 1.0 = last. Uses the loaded range, so a batch of Ep 51-100 works too."""
    nums = sorted(eps)
    if len(nums) < 2:
        return 0.0
    return (ep_num - nums[0]) / (nums[-1] - nums[0])


def score_promo(p: Promo, names: set[str], premise: set[str], eps: dict[int, Episode]) -> Promo:
    beats = p.beats
    first, last = p.segments[0], p.segments[-1]
    hb = _hook_of(first.beats, first.start) or p.hook_beat
    cb = _cliff_of(last.beats, last.end) or p.cliff_beat
    p.hook_beat, p.cliff_beat = hb, cb
    jumps = sum(len({b.scene for b in s.beats}) - 1 for s in p.segments)
    body, sag = _body_multi(p)
    stand, flags = standalone_score(beats, names, jumps)
    if p.kind == "stitched":
        stand = max(0.0, stand - 0.05 * (len(p.segments) - 1))
    p.tropes = _tropes(beats)
    w_all = sum(L.TROPES[t][2] for b in beats for t in b.tropes)
    w_prem = sum(L.TROPES[t][2] for b in beats for t in b.tropes if t in premise)
    prem = round(min(1.0, 0.3 * bool(w_all) + 1.4 * w_prem / w_all), 3) if w_all else 0.0
    p.scores = dict(hook=round(hook_strength(hb, first.start), 3), cliff=round(cb.cliff, 3), body=body, standalone=stand,
                    fit=round(fit_score(p.duration), 3), premise=prem, sag=sag)
    p.scores["total"] = _total(p.scores)
    late = season_pos(min(p.episodes), eps) > 0.6
    if late:
        flags.append(f"From late in the season (Ep {min(p.episodes)}): may spoil or need context")
    if hb.kind in ("action", "camera", "sfx"):
        flags.append("The hook is visual: check it reads on screen")
    if sag > 12:
        flags.append(f"Slow stretch: {sag:.0f} s without a strong moment")
    p.flags = flags
    return p


def _body_multi(p: Promo) -> tuple[float, float]:
    qs, sags, w = [], [], []
    for s in p.segments:
        q, sag = body_score(s.beats, s.start, s.end)
        qs.append(q * s.dur)
        sags.append(sag)
        w.append(s.dur)
    return round(sum(qs) / max(1e-6, sum(w)), 3), max(sags)


# ----------------------------------------------------------------- generators
def single_candidates(ep: Episode, names, premise, eps, hook_min=0.42, cliff_min=0.45) -> list[Promo]:
    starts, ends = cut_points(ep)
    hooks = [b for b in ep.beats if b.hook >= hook_min and b.kind != "camera"] + \
            [b for b in ep.beats if b.kind == "camera" and b.hook >= 0.7]
    cliffs = [b for b in ep.beats if b.cliff >= cliff_min]
    out = []
    seen = set()
    for h in hooks:
        s = _start_for(h, starts)
        if s is None:
            continue
        for c in cliffs:
            e = _end_for(c, ends)
            if e is None or not (MIN_LEN <= e - s <= MAX_LEN) or (s, e) in seen:
                continue
            seen.add((s, e))
            seg = Segment(ep.num, s, e, _inside(ep, s, e))
            out.append(score_promo(Promo("single", [seg], h, c), names, premise, eps))
    return out


def _top_nonoverlap(cands, k):
    cands.sort(key=lambda x: -x[0])
    picked: list[Segment] = []
    for q, seg in cands:
        if all(seg.end <= p.start or seg.start >= p.end for p in picked):
            picked.append(seg)
        if len(picked) == k:
            break
    return picked


def moments(ep: Episode, k: int = 3) -> tuple[list[Segment], list[Segment]]:
    """Short building blocks for stitched promos.
    openers: 5-18 s that START on a strong hook.   closers: 6-22 s that END on a strong cliffhanger."""
    starts, ends = cut_points(ep)
    ops, cls = [], []
    for h in [b for b in ep.beats if b.hook >= 0.55 and b.kind != "camera"]:
        s = _start_for(h, starts)
        if s is None:
            continue
        for e in ends:
            if 5 <= e - s <= 18 and (bs := _inside(ep, s, e)):
                ops.append((0.6 * h.hook + 0.4 * max(b.heat for b in bs), Segment(ep.num, s, e, bs)))
    for c in [b for b in ep.beats if b.cliff >= 0.6]:
        e = _end_for(c, ends)
        if e is None:
            continue
        for s in starts:
            if 6 <= e - s <= 22 and (bs := _inside(ep, s, e)):
                first = next((b for b in bs if b.kind == "dialogue"), None)
                ctx = first.context if first else 0.0
                cls.append((0.6 * c.cliff + 0.4 * max(b.heat for b in bs) - 0.3 * ctx, Segment(ep.num, s, e, bs)))
    return _top_nonoverlap(ops, k), _top_nonoverlap(cls, k)


def _after(a: Segment, b: Segment) -> bool:
    return (b.ep > a.ep) or (b.ep == a.ep and b.start >= a.end + 3.0)


def stitched_candidates(episodes: list[Episode], names, premise, eps, span=4,
                        title_tropes: set[str] | None = None) -> list[Promo]:
    openers, closers = [], []
    for ep in episodes:
        o, c = moments(ep)
        openers += o
        closers += c
    tt = title_tropes or premise
    has = lambda m, ts: bool({t for b in m.beats for t in b.tropes} & ts)  # noqa: E731
    first_eps = sorted({m.ep for m in openers + closers})[:5]
    strength = lambda m: max(b.hook for b in m.beats) + max(b.cliff for b in m.beats)  # noqa: E731
    # premise trailers open on the setup (first 5 episodes) and end on the title's payoff. The pools are
    # capped to the strongest moments so long seasons don't blow up quadratically (no effect at 50 episodes).
    p_open = [m for m in openers if has(m, premise) and m.ep in first_eps]
    p_any = sorted((m for m in openers + closers if has(m, premise)), key=lambda m: -strength(m))[:60]
    p_close = sorted((m for m in closers if has(m, tt) and m.ep not in first_eps), key=lambda m: -strength(m))[:20]
    out, seen = [], set()

    def build(combo):
        key = tuple((m.ep, m.start, m.end) for m in combo)
        if key in seen or not all(_after(a, b) for a, b in zip(combo, combo[1:])):
            return
        seen.add(key)
        if not (25 <= sum(m.dur for m in combo) <= MAX_LEN):
            return
        cb = _cliff_of(combo[-1].beats, combo[-1].end)
        if cb is None or cb.cliff < 0.55:
            return
        hb = _hook_of(combo[0].beats, combo[0].start)
        p = score_promo(Promo("stitched", list(combo), hb, cb), names, premise, eps)
        spk = [{b.speaker for b in m.beats if b.speaker} for m in combo]
        shared = sum(bool(x & y) for x, y in zip(spk, spk[1:])) / (len(combo) - 1)
        # stitched promos: small bonus when consecutive cuts share a speaker (easier to follow),
        # small cost for a third cut (each cut is one more jump for a new viewer)
        p.scores["stitch_adj"] = round(0.04 * shared - 0.03 * (len(combo) - 2), 4)
        p.scores["total"] = round(p.scores["total"] + p.scores["stitch_adj"], 4)
        out.append(p)

    # 1) arc promos: an opener and a closer (optionally a middle) from the same or neighbouring episodes
    for a in openers:
        near_c = [c for c in closers if 0 <= c.ep - a.ep <= span]
        near_m = [m for m in openers + closers if 0 <= m.ep - a.ep <= span]
        for c in near_c:
            build((a, c))
            for m in near_m:
                if a.ep <= m.ep <= c.ep:
                    build((a, m, c))
    # 2) premise trailers: setup from the first episodes -> payoff anywhere, all selling the title promise
    for a in p_open:
        for c in p_close:
            build((a, c))
            for m in p_any:
                build((a, m, c))
    return out
