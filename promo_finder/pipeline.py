"""End-to-end run: scripts in -> ranked promos out."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .candidates import Promo, score_promo, single_candidates, stitched_candidates
from .llm import Judge
from .parser import Episode
from .rank import post_order, select, why_line
from .scoring import character_names, premise_tropes, score_episodes


@dataclass
class Result:
    title: str
    model: str
    episodes: list[Episode]
    promos: list[Promo]
    candidates: list[Promo]
    by_episode: list[Promo]
    premise: set[str]
    stats: dict = field(default_factory=dict)
    log: list[str] = field(default_factory=list)


def run(episodes: list[Episode], title: str = "Untitled show", model: str | Judge = "rules",
        n_single: int = 20, n_stitched: int = 6, llm_top: int = 40, progress=None,
        warnings: list[str] | None = None) -> Result:
    """model: a spec string like 'gemini:gemini-3.8-flash', or a ready Judge (the app passes one so
    the API key never goes through os.environ). warnings: loader warnings to include in the log."""
    t0 = time.time()
    log = []
    say = lambda m: (log.append(m), progress and progress(m))  # noqa: E731
    for w in warnings or []:
        say(f"Warning: {w}")
    eps = {e.num: e for e in episodes}
    if len(eps) != len(episodes):  # callers that skip the loader can still pass duplicates
        say(f"Warning: {len(episodes) - len(eps)} duplicate episode number(s); keeping one of each")
        episodes = sorted(eps.values(), key=lambda e: e.num)
    score_episodes(episodes)
    premise = premise_tropes(title, episodes)
    title_tropes = premise_tropes(title, [])
    names = character_names(episodes)
    say(f"Parsed {len(episodes)} episodes, {sum(len(e.beats) for e in episodes)} beats, "
        f"{sum(e.duration for e in episodes) / 60:.1f} min of story.")
    say(f"Premise tropes from title + first loglines: {', '.join(sorted(premise)) or 'none'}")

    singles: list[Promo] = []
    for ep in episodes:
        singles += single_candidates(ep, names, premise, eps)
    stitched = stitched_candidates(episodes, names, premise, eps, title_tropes=title_tropes) \
        if n_stitched else []
    stitched_all = stitched
    say(f"Generated {len(singles)} single-clip and {len(stitched)} stitched candidates.")

    all_singles = singles
    n_candidates = len(singles) + len(stitched)
    judge = model if isinstance(model, Judge) else Judge(model)
    mode = "rules"
    ai = {}
    if judge.active:
        ai = {"requested": judge.spec}
        ok, why_not = judge.ready()
        if not ok:
            say(f"AI judge {judge.spec} not used: {why_not}. Ranking with rules only.")
        else:
            # Only the best rules-ranked, non-overlapping candidates go to the model: bounded cost.
            shortlist = select(singles, llm_top, per_ep=3, max_overlap=0.5) + \
                        select(stitched, max(6, llm_top // 4), max_overlap=0.2)
            premise_txt = (episodes[0].logline if episodes else "")
            label = "MOCK judge (test only, not a real model)" if judge.is_mock else f"AI judge {judge.spec}"
            say(f"{label}: rating {len(shortlist)} shortlisted candidates…")
            rescore = lambda p: score_promo(p, names, premise, eps)  # noqa: E731
            review_started = time.monotonic()
            for i, p in enumerate(shortlist, 1):
                if time.monotonic() - review_started >= 60:
                    judge.tripped = "stopped starting new reviews after the 60-second AI review budget"
                    break
                say(f"  Reviewing candidate {i}/{len(shortlist)}…")
                judge.judge(p, title, premise_txt, eps, rescore=rescore)
                if p.llm and "error" in p.llm:
                    detail = str(p.llm["error"])
                    if judge.api_key:
                        detail = detail.replace(judge.api_key, "[redacted]")
                    say(f"  Candidate {i}: review failed ({detail}); keeping rules score.")
                else:
                    say(f"  Candidate {i}: review complete.")
                if judge.tripped:
                    break
            judged = sum(1 for p in shortlist if p.llm and "error" not in p.llm)
            ai = dict(judge.stats, requested=judge.spec, shortlisted=len(shortlist), judged=judged, stopped=judge.tripped)
            say(f"  {judged}/{len(shortlist)} rated by the model "
                f"({judge.stats['calls']} calls, {judge.stats['cached']} from cache, {judge.stats['failed']} failed, "
                f"{judge.stats['trims_applied']} trims applied, {judge.stats['trims_rejected']} rejected).")
            if ai.get("usage_calls"):
                say(f"  Reported API usage ({ai['usage_calls']} responses): {ai['prompt_tokens']} input tokens, "
                    f"{ai['completion_tokens']} output tokens (includes {ai['reasoning_tokens']} reasoning tokens).")
                if "estimated_cost_inr" in ai:
                    say(f"  Estimated Sarvam model cost from reported usage: INR {ai['estimated_cost_inr']:.4f} "
                        "(excludes tax; cached replies add no API usage; dashboard is authoritative).")
            if judge.tripped:
                say(f"  AI judge {judge.tripped}; the rest keep their rules score.")
            if judged:
                mode = judge.spec
                singles = [p for p in shortlist if p.kind == "single"]
                stitched = [p for p in shortlist if p.kind == "stitched"]
            else:
                say("  No candidate was rated, so the ranking below is rules only.")
                for p in shortlist:
                    p.llm = None

    # Ranked list: singles and stitched compete on one score, with a cap on stitched promos.
    best = select(singles + stitched, n_single + n_stitched, per_ep=1, max_overlap=0.25,
                  caps={"single": n_single, "stitched": n_stitched}, no_shared_beats=True)
    ordered = post_order(best, eps, premise)
    # Library: the best clean single-clip promo for EVERY episode (an editor's menu, not a post plan).
    by_ep = []
    per_ep: dict[int, list[Promo]] = {}
    for p in all_singles:
        per_ep.setdefault(p.episodes[0], []).append(p)
    for ep in episodes:
        mine = per_ep.get(ep.num, [])
        # rules score only, so AI-judged and un-judged clips are compared on the same scale
        by_ep += select(mine, 1, key=lambda p: p.scores.get("rules_total", p.scores["total"]))
    for p in by_ep:
        p.id = p.id or f"E{p.episodes[0]:02d}"
    for p in ordered + by_ep:
        if not p.why:
            p.why = why_line(p, premise)
    covered = sorted({e for p in ordered for e in p.episodes})
    stats = dict(episodes=len(episodes), beats=sum(len(e.beats) for e in episodes),
                 minutes=round(sum(e.duration for e in episodes) / 60, 1),
                 candidates=n_candidates, promos=len(ordered),
                 episodes_covered=len(covered), seconds=round(time.time() - t0, 1), model=mode,
                 model_requested=judge.spec, ai=ai)
    say(f"Selected {len(ordered)} promos covering {len(covered)} episodes in {stats['seconds']}s.")
    stats["library"] = len(by_ep)
    return Result(title, mode, episodes, ordered, all_singles + stitched_all, by_ep, premise, stats, log)
