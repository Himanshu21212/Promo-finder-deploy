"""Edge cases: bad input, odd episodes, invalid cuts, and a misbehaving AI model.

Technical validation only. These tests check that the output is *well-formed and safe*
(timestamps real, rules kept, no crashes). Whether a promo is *good* is a separate, subjective
question that tests can't answer; see evaluation/spot_check_top16.md for that.
"""
import io
import json
import zipfile
from pathlib import Path

import pytest
import requests

from promo_finder import cli
from promo_finder.candidates import Promo, Segment, _inside, _utterances, season_pos
from promo_finder.checks import run_checks
from promo_finder.llm import Judge, _apply_trim, _json, _score
from promo_finder.parser import finalize, load_zip_bytes, parse_text
from promo_finder.pipeline import run

from helpers import DRAMA, script


def eps_from(*texts, names=None):
    w = []
    eps = finalize([parse_text(t, (names or [f"episode-{i + 1:03d}.txt" for i in range(len(texts))])[i])
                    for i, t in enumerate(texts)], w)
    return eps, w


def all_cut_points_real(r):
    """Every segment boundary must be a beat start/end (or the episode end) from the script."""
    eps = {e.num: e for e in r.episodes}
    for p in r.promos + r.by_episode:
        for s in p.segments:
            ep = eps[s.ep]
            starts = {round(b.start, 2) for b in ep.beats}
            ends = {round(b.end, 2) for b in ep.beats} | {round(ep.duration, 2)}
            assert round(s.start, 2) in starts and round(s.end, 2) in ends, (p.id, s.start, s.end)


# ----------------------------------------------------------------- input format
def test_blocks_without_timestamps_are_skipped_and_reported():
    text = script(1, DRAMA).replace("Start: (00:00.10) | End: (00:01.90)", "", 1)
    text = text.replace('**ACTION:**\nStart: (00:00.00) | End: (00:02.00)', '**ACTION:**', 1)
    eps, w = eps_from(text)
    assert eps and len(eps[0].beats) > 10
    assert any("no Start/End time" in x for x in w)


def test_file_in_wrong_format_is_dropped_with_a_warning():
    good = script(1, DRAMA)
    eps, w = eps_from(good, "Dear diary, today nothing happened.\nThe end.")
    assert [e.num for e in eps] == [1]
    assert any("no timestamped lines" in x for x in w)


def test_duplicate_episode_numbers_keep_one():
    a, b = script(3, DRAMA), script(3, DRAMA[:5])
    eps, w = eps_from(a, b, names=["ep3-full.txt", "ep3-short.txt"])
    assert len(eps) == 1 and eps[0].source == "ep3-full.txt"
    assert any("Two files claim Episode 3" in x for x in w)


def test_missing_episode_numbers_get_unique_numbers():
    eps, w = eps_from(script(None, DRAMA), script(None, DRAMA), names=["a.txt", "b.txt"])
    assert sorted(e.num for e in eps) == [1, 2]
    assert all(b.ep == e.num for e in eps for b in e.beats)


def test_hour_style_timestamps_parse():
    ep = parse_text(script(1, DRAMA, hours=True), "x.txt")
    assert len(ep.beats) > 20 and abs(ep.duration - sum(d for *_, d in DRAMA)) < 0.01


def test_missing_scene_boundaries_and_header():
    ep = parse_text(script(1, DRAMA, scenes=False, header=False), "episode-007.txt")
    assert ep.num == 7 and len(ep.scenes) == 1 and ep.beats


def test_zip_with_only_junk_makes_the_cli_fail_cleanly(tmp_path, capsys):
    z = tmp_path / "junk.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("readme.txt", "not a screenplay")
    assert cli.main([str(z), "-o", str(tmp_path / "out")]) == 1
    assert "No episodes found" in capsys.readouterr().err


# ----------------------------------------------------------------- odd episodes
def test_actions_only_episode_does_not_crash():
    beats = [("ACTION", "", "Rain falls on an empty street.", 5.0)] * 12
    eps, _ = eps_from(script(1, beats))
    r = run(eps, "quiet show")
    assert run_checks(r)["passed"] == run_checks(r)["checked"]


def test_very_short_episode_gives_no_single_clip():
    eps, _ = eps_from(script(1, DRAMA[:4]))           # about 10 s long
    r = run(eps, "short")
    assert not [p for p in r.candidates if p.kind == "single"]
    assert r.by_episode == []


def test_very_long_episode_keeps_every_rule():
    eps, _ = eps_from(script(1, DRAMA * 16))          # about 10 minutes
    r = run(eps, "long")
    assert r.promos
    c = run_checks(r)
    assert c["passed"] == c["checked"]
    assert all(20 <= p.duration <= 60 and p.hook_at <= 3.0 for p in r.promos)
    all_cut_points_real(r)


def test_calm_episode_has_no_usable_candidate():
    calm = [("ANNA", "Soft", "The tea is ready.", 3.0), ("BEN", "Calm", "Thank you, it smells nice.", 3.0)] * 8
    eps, _ = eps_from(script(1, DRAMA), script(2, calm))
    r = run(eps, "mixed")
    assert 2 not in {e for p in r.promos for e in p.episodes}
    assert 2 not in {p.episodes[0] for p in r.by_episode}


def test_episode_numbers_need_not_start_at_one():
    eps, _ = eps_from(script(51, DRAMA), script(52, DRAMA), script(60, DRAMA))
    d = {e.num: e for e in eps}
    assert season_pos(51, d) == 0.0 and season_pos(60, d) == 1.0
    r = run(eps, "batch two")
    first = [p for p in r.promos if min(p.episodes) == 51]
    assert first and not any("late in the season" in f for p in first for f in p.flags)


# ----------------------------------------------------------------- ranked list integrity
def test_ranked_list_has_no_overlaps_or_repeated_beats():
    eps, _ = eps_from(*(script(i, DRAMA * 3) for i in range(1, 6)))
    r = run(eps, "repeats")
    seen_keys = []
    for p in r.promos:
        keys = {(p.hook_beat.ep, p.hook_beat.idx), (p.cliff_beat.ep, p.cliff_beat.idx)}
        for q, qkeys in seen_keys:
            qbeats = {(b.ep, b.idx) for b in q.beats if b.kind != "camera"}
            pbeats = {(b.ep, b.idx) for b in p.beats if b.kind != "camera"}
            assert not (keys & qbeats) and not (qkeys & pbeats), (p.id, q.id)
            for s in p.segments:
                for t in q.segments:
                    if s.ep == t.ep:
                        inter = max(0.0, min(s.end, t.end) - max(s.start, t.start))
                        assert inter <= 0.25 * min(s.dur, t.dur) + 1e-6
        seen_keys.append((p, keys))


def test_checks_catch_invalid_cuts():
    """The validator itself must fail bad promos (too long, late hook, mid-line cut, made-up time, wrong order)."""
    eps, _ = eps_from(script(1, DRAMA * 3), script(2, DRAMA))
    r = run(eps, "validator")
    ep = r.episodes[0]
    line = next(b for b in ep.lines if b.end - b.start > 1.5)
    bad = [
        Segment(1, 0.0, 70.0, _inside(ep, 0.0, 70.0)),                           # too long
        Segment(1, line.start + 0.7, line.start + 30.7, []),                       # starts inside a line, invented time
    ]
    p1 = Promo("single", [bad[0]], ep.beats[0], ep.beats[-1], id="BAD1")
    p2 = Promo("single", [bad[1]], ep.beats[0], ep.beats[-1], id="BAD2")
    late = Promo("single", [Segment(1, 0.0, 30.0, _inside(ep, 0.0, 30.0))], ep.lines[8], ep.lines[9], id="BAD3")
    order = Promo("stitched", [Segment(2, 0.0, 12.0, []), Segment(1, 0.0, 12.0, [])], ep.beats[0], ep.beats[1], id="BAD4")
    r.promos = r.promos + [p1, p2, late, order]
    rows = {x["id"]: x for x in run_checks(r)["rows"]}
    assert not rows["BAD1"]["pass"] and any("outside 20-60s" in f for f in rows["BAD1"]["fails"])
    assert any("inside a spoken line" in f for f in rows["BAD2"]["fails"])
    assert any("not a timestamp from the script" in f for f in rows["BAD2"]["fails"])
    assert any("hook lands" in f for f in rows["BAD3"]["fails"])
    assert any("story order" in f for f in rows["BAD4"]["fails"])


def test_ai_trims_that_break_rules_are_rejected():
    eps, _ = eps_from(script(1, DRAMA * 2), script(2, DRAMA))
    d = {e.num: e for e in eps}
    r = run(eps, "trims")
    p = next(p for p in r.candidates if p.kind == "single" and p.duration > 30)
    seg = p.segments[0]
    lines = [b for b in seg.beats if b.kind == "dialogue"]
    other_ep_beat = d[2].lines[0]
    before = (seg.start, seg.end)
    assert _apply_trim(p, lines[0], lines[1], d).startswith("rejected")            # far too short
    assert _apply_trim(p, other_ep_beat, None, d).startswith("rejected")           # beat from another episode
    outside = next((b for b in d[1].beats if b.start < seg.start - 5), None)
    if outside:
        assert _apply_trim(p, outside, None, d).startswith("rejected")             # may only shorten
    assert (p.segments[0].start, p.segments[0].end) == before


# ----------------------------------------------------------------- AI judge robustness
def _ai_run(transport, **kw):
    eps, _ = eps_from(*(script(i, DRAMA * 2) for i in range(1, 4)))
    j = Judge("custom:test", base_url="http://unused", use_cache=False, min_interval=0, transport=transport)
    return run(eps, "ai test", model=j, llm_top=8, **kw), j


def test_reply_parsing_is_forgiving():
    assert _json('Sure! ```json\n{"hook": 8, "x": {"y": 1}}\n``` hope that helps')["hook"] == 8
    assert _score("8/10") == 8.0 and _score("80%") == 8.0 and _score(85) == 8.5 and _score("high") is None
    assert _score(0) == 1.0 and _score(14) == 1.4 and _score(None) is None


def test_malformed_ai_replies_never_crash_the_run():
    replies = iter(["no json here", '{"hook": "great"}', '{"hook": "8/10", "cliffhanger": "7", "standalone": 6, '
                    '"overall": 7, "hook_beat": 99, "cliff_beat": "abc", "why": "ok", "risk": ""}'] * 50)
    r, j = _ai_run(lambda prompt: next(replies))
    assert r.promos and j.stats["failed"] > 0
    rated = [p for p in r.candidates if p.llm and "overall" in p.llm]
    assert rated and all(p.llm["hook"] == 8.0 for p in rated)
    assert run_checks(r)["passed"] == run_checks(r)["checked"]


def test_ai_can_not_move_timestamps():
    def sneaky(prompt):
        # tries to trim to beats 1..3 (too short), and names out-of-range hook / cliff beats
        return json.dumps({"hook": 9, "cliffhanger": 9, "standalone": 9, "overall": 9, "hook_beat": 40,
                           "cliff_beat": 0, "trim_start_beat": 1, "trim_end_beat": 3, "why": "x", "risk": ""})
    r, j = _ai_run(sneaky)
    assert j.stats["trims_applied"] == 0 and j.stats["trims_rejected"] > 0
    all_cut_points_real(r)
    assert run_checks(r)["passed"] == run_checks(r)["checked"]


def test_circuit_breaker_stops_a_broken_endpoint():
    calls = {"n": 0}

    def down(prompt):
        calls["n"] += 1
        raise requests.ConnectionError("refused")
    import promo_finder.llm as llm
    real_sleep, llm.time.sleep = llm.time.sleep, (lambda s: None)
    try:
        r, j = _ai_run(down)
    finally:
        llm.time.sleep = real_sleep
    assert j.tripped and calls["n"] == 3 * 2           # 3 candidates x 2 attempts, then it stops
    assert r.model == "rules" and r.promos              # falls back to the rules ranking
    assert any("rules only" in line for line in r.log)


def test_rate_limit_is_retried():
    state = {"n": 0}

    def flaky(prompt):
        state["n"] += 1
        if state["n"] == 1:
            resp = requests.Response()
            resp.status_code = 429
            resp.headers["Retry-After"] = "0"
            raise requests.HTTPError(response=resp)
        return json.dumps({"hook": 7, "cliffhanger": 7, "standalone": 7, "overall": 7, "why": "ok", "risk": ""})
    r, j = _ai_run(flaky)
    assert j.stats["failed"] == 0 and r.model.startswith("custom")


def test_missing_api_key_falls_back_to_rules(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    eps, _ = eps_from(script(1, DRAMA * 2))
    r = run(eps, "no key", model="gemini")
    assert r.model == "rules" and any("not used: no GEMINI_API_KEY" in line for line in r.log)


# ----------------------------------------------------------------- reproducibility
def test_same_input_same_output():
    eps1, _ = eps_from(*(script(i, DRAMA * 2) for i in range(1, 4)))
    eps2, _ = eps_from(*(script(i, DRAMA * 2) for i in range(1, 4)))
    key = lambda r: [(p.kind, [(s.ep, s.start, s.end) for s in p.segments]) for p in r.promos]  # noqa: E731
    assert key(run(eps1, "x")) == key(run(eps2, "x"))


def test_cli_end_to_end_on_a_zip(tmp_path):
    z = tmp_path / "My Show-scripts.zip"
    with zipfile.ZipFile(z, "w") as f:
        for i in (1, 2):
            f.writestr(f"My Show/episode-{i:03d}.txt", script(i, DRAMA * 2))
    out = tmp_path / "out"
    assert cli.main([str(z), "-o", str(out)]) == 0
    data = json.loads((out / "promos.json").read_text())
    assert data["show"] == "My Show" and data["ranked_promos"]
    for name in ("promo_report.html", "promos_ranked.csv", "promos_by_episode.csv", "quality_checks.md"):
        assert (out / name).stat().st_size > 0


def test_app_loads_and_runs_the_demo():
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=60).run()
    assert not at.exception
    demo = next(b for b in at.sidebar.button if b.label == "Try the demo script")
    demo.click().run()
    assert not at.exception
    assert "result" in at.session_state
