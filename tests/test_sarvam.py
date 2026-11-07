"""API-contract and fallback checks using simulated HTTP replies, never real credits."""
import json
from pathlib import Path

import pytest
import requests

from promo_finder import load_path
from promo_finder.checks import run_checks
from promo_finder.llm import Judge
from promo_finder.pipeline import run
from promo_finder.report import to_json
from promo_finder.ui import mode_badge

DEMO = Path(__file__).resolve().parents[1] / "samples" / "demo_show.zip"
KEY = "test-key-not-a-real-secret"
RATING = json.dumps({"hook": 8, "cliffhanger": 7, "standalone": 8, "overall": 8,
                     "hook_beat": 1, "cliff_beat": 999, "trim_start_beat": None,
                     "trim_end_beat": None, "why": "Simulated HTTP response for a test.", "risk": ""})


def response(content=RATING, finish="stop", status=200):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps({
        "choices": [{"message": {"content": content, "reasoning_content": RATING}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500,
                  "prompt_tokens_details": {"cached_tokens": 100},
                  "completion_tokens_details": {"reasoning_tokens": 300}},
        "error": {"message": f"Rejected credential: {KEY}"},
    }).encode()
    return r


def judge():
    return Judge("sarvam:sarvam-105b", api_key=KEY, min_interval=0, use_cache=False)


def test_sarvam_request_usage_and_timestamp_guards(monkeypatch):
    sent = []

    def post(url, **kwargs):
        sent.append((url, kwargs))
        return response()

    monkeypatch.setattr("promo_finder.llm.requests.post", post)
    j = judge()
    r = run(load_path(DEMO), "The Maid Was the Heiress", j, llm_top=10)
    assert r.model == j.spec and r.stats["ai"]["judged"] > 0
    assert run_checks(r)["passed"] == run_checks(r)["checked"]
    assert sent and all(url == "https://api.sarvam.ai/v2/chat/completions" for url, _ in sent)
    for _, request in sent:
        assert request["headers"]["Authorization"] == f"Bearer {KEY}"
        assert request["json"]["model"] == "sarvam-105b"
        assert request["json"]["response_format"] == {"type": "json_object"}
        assert request["json"]["max_tokens"] == 4096
    assert j.stats["prompt_tokens"] == 1000 * len(sent)
    assert j.stats["completion_tokens"] == 500 * len(sent)
    assert j.stats["reasoning_tokens"] == 300 * len(sent)
    # Reasoning is already included in completion_tokens; do not bill it twice.
    assert j.stats["estimated_cost_inr"] == pytest.approx(0.044 * len(sent))
    assert KEY not in to_json(r) and KEY not in "\n".join(r.log)


@pytest.mark.parametrize("status", [401, 402, 403, 404])
def test_permanent_api_errors_stop_immediately_and_report_rules(monkeypatch, status):
    sent = []
    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: sent.append(1) or response(status=status))
    j = judge()
    r = run(load_path(DEMO), "demo", j, llm_top=10)
    assert len(sent) == 1 and j.tripped
    assert r.model == "rules" and r.promos
    assert r.stats["ai"]["judged"] == 0
    badge = mode_badge(r.model, r.stats["ai"])
    assert "no usable ratings" in badge and "no AI model was called" not in badge
    assert KEY not in to_json(r) and KEY not in "\n".join(r.log)


@pytest.mark.parametrize("content,finish", [(None, "stop"), ("", "stop"), (RATING, "length"), ("not JSON", "stop")])
def test_unusable_or_truncated_replies_never_become_ai_ratings(monkeypatch, content, finish):
    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: response(content, finish))
    j = judge()
    r = run(load_path(DEMO), "demo", j, llm_top=10)
    assert r.model == "rules" and r.promos
    assert j.stats["calls"] == j.stats["failed"] == 3
    assert j.stats["completion_tokens"] == 1500  # even unusable replies consume credits
    assert j.tripped


def test_missing_sarvam_key_is_reported_without_making_requests(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: pytest.fail("must not call without a key"))
    r = run(load_path(DEMO), "demo", "sarvam")
    assert r.model == "rules" and r.stats["model_requested"] == "sarvam"
    assert r.stats["ai"]["requested"] == "sarvam"
    assert "no SARVAM_API_KEY" in "\n".join(r.log)
    assert "no API requests made" in mode_badge(r.model, r.stats["ai"])


def test_streamlit_uses_sarvam_secret_and_displays_usage(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: response())
    monkeypatch.setattr("promo_finder.llm.time.sleep", lambda _: None)
    app = AppTest.from_file(str(DEMO.parents[1] / "app.py"), default_timeout=30)
    app.secrets["SARVAM_API_KEY"] = KEY
    app.run()
    assert not app.exception
    assert app.selectbox[0].value == "Sarvam (recommended)"
    next(b for b in app.button if b.label == "Try the demo script").click().run()
    assert not app.exception
    result = app.session_state["result"]
    assert result.model == "sarvam:sarvam-105b"
    assert result.stats["ai"]["judged"] > 0
    assert result.stats["ai"]["usage_calls"] > 0
