import requests
from promo_finder.llm import Judge
from promo_finder.pipeline import run
from helpers import script, DRAMA
from promo_finder.parser import finalize, parse_text


def eps_from(*texts):
    warnings = []
    return finalize([parse_text(text, f"episode-{i}.txt") for i, text in enumerate(texts)], warnings), warnings


def test_timeouts_are_not_retried_and_each_candidate_has_progress(monkeypatch):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs)
        raise requests.Timeout()
    monkeypatch.setattr("promo_finder.llm.requests.post", post)
    eps, _ = eps_from(*(script(i, DRAMA * 2) for i in range(1, 4)))
    j = Judge("sarvam:sarvam-105b", api_key="test-only",
              min_interval=0, use_cache=False)
    progress = []
    result = run(eps, "test", j, progress=progress.append)
    assert len(calls) == 1 and all(c["timeout"] == (5, 35) for c in calls)
    assert result.stats["ai"]["error_kind"] == "timeout"
    assert result.model == "rules" and result.promos
    assert any("Reviewing candidate 1/" in line for line in progress)
    assert any("timed out" in line for line in progress)


def test_review_budget_stops_starting_new_calls(monkeypatch):
    elapsed = [0]
    def transport(prompt):
        elapsed[0] += 61
        return '{"hook":7,"cliffhanger":7,"standalone":7,"overall":7}'
    monkeypatch.setattr("promo_finder.pipeline.time.monotonic", lambda: elapsed[0])
    eps, _ = eps_from(*(script(i, DRAMA * 2) for i in range(1, 4)))
    j = Judge("custom:test", transport=transport, min_interval=0, use_cache=False)
    result = run(eps, "test", j)
    assert j.stats["calls"] == 1
    assert result.stats["ai"]["judged"] == 1
    assert "60-second" in result.stats["ai"]["stopped"]
