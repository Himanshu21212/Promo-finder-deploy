"""Smoke tests on the original demo script (no confidential data needed).   Run:  python -m pytest -q"""
from pathlib import Path

from promo_finder import load_path, run
from promo_finder.checks import run_checks
from promo_finder.llm import Judge, _apply_trim

DEMO = Path(__file__).resolve().parents[1] / "samples" / "demo_show.zip"


def test_parser_reads_every_beat():
    eps = load_path(DEMO)
    assert [e.num for e in eps] == [1, 2]
    assert all(e.lines and e.shots for e in eps)
    assert eps[0].lines[0].speaker == "VICTORIA" and "Mocking" in eps[0].lines[0].tags


def test_rules_run_passes_hard_checks():
    r = run(load_path(DEMO), "The Maid Was the Heiress")
    assert r.promos, "should find at least one promo"
    c = run_checks(r)
    assert c["passed"] == c["checked"]
    for p in r.promos:
        assert 20 <= p.duration <= 60 and p.hook_at <= 3.0
    assert r.model == "rules"


def test_mock_judge_path_runs_and_is_labelled():
    r = run(load_path(DEMO), "The Maid Was the Heiress", model=Judge("mock", use_cache=False), llm_top=10)
    assert r.model == "mock"
    assert any(p.llm and "overall" in p.llm for p in r.promos)
    assert all("MOCK" in p.why for p in r.promos if p.llm and "overall" in p.llm)
    assert any("MOCK" in line for line in r.log)


def test_bad_ai_trim_is_rejected():
    eps = load_path(DEMO)
    r = run(eps, "demo")
    p = next(p for p in r.candidates if p.kind == "single")
    first = p.segments[0].beats[0]
    msg = _apply_trim(p, first, first, {e.num: e for e in eps})   # would make a ~2 s clip
    assert msg.startswith("rejected")


def test_unknown_provider_errors():
    try:
        Judge("nope:model")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
