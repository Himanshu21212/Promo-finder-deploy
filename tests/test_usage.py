"""Credit estimates must stay honest across rerenders, missing usage and balance snapshots."""
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from promo_finder.usage import SarvamConfig, UsageLedger
from test_sarvam import KEY, response

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "samples" / "demo_show.zip"


def stats(cost="0.25", calls=1, usage_calls=1):
    return {"calls": calls, "usage_calls": usage_calls, "prompt_tokens": 100,
            "completion_tokens": 50, "estimated_cost_inr": cost}


def test_snapshots_include_only_future_spend_and_do_not_double_charge():
    ledger = UsageLedger()
    ledger.record("old", stats("2.50"))
    ledger.set_snapshot("89")
    assert ledger.remaining == Decimal("89")
    ledger.record("new", stats("0.25"))
    ledger.record("new", stats("0.25"))
    assert ledger.remaining == Decimal("88.75")
    ledger.record("new", stats("0.40", calls=2, usage_calls=2))
    assert ledger.remaining == Decimal("88.60")
    assert ledger.spend == Decimal("2.90")
    assert ledger.total("calls") == 3


def test_unknown_usage_hides_remaining_until_a_fresh_snapshot():
    ledger = UsageLedger()
    assert ledger.remaining is None
    ledger.set_snapshot("10")
    ledger.record("missing", {"calls": 1, "usage_calls": 0})
    assert ledger.remaining is None
    assert ledger.unreported == 1
    ledger.set_snapshot("9")  # actual dashboard balance reconciles prior unknown requests
    ledger.record("new", stats("0.50"))
    assert ledger.remaining == Decimal("8.50")


@pytest.mark.parametrize("value", [None, "NaN", "Infinity", "-1", "not money"])
def test_invalid_snapshot_is_not_shown_as_a_balance(value):
    ledger = UsageLedger()
    with pytest.raises(ValueError):
        ledger.set_snapshot(value)
    assert ledger.remaining is None


def test_zero_balance_is_valid_and_estimate_never_goes_negative():
    ledger = UsageLedger()
    ledger.set_snapshot(0)
    ledger.record("run", stats("0.01"))
    assert ledger.remaining == 0


def test_missing_cost_is_unknown_even_if_token_counters_exist():
    ledger = UsageLedger()
    ledger.set_snapshot("10")
    ledger.record("unknown", stats(None))
    assert ledger.remaining is None


def test_legacy_sarvam_credentials_work_without_exposing_configuration():
    config = SarvamConfig.load({"LLM_API_KEY": KEY, "LLM_BASE_URL": "https://api.sarvam.ai/v1/"}.get)
    assert config.configured and config.base_url == "https://api.sarvam.ai/v1"
    assert KEY not in repr(config)
    assert config.scope != SarvamConfig(api_key="another-test-key").scope


def test_other_provider_keys_are_not_treated_as_sarvam():
    for base in ["https://api.other.example/v1", "https://api.sarvam.ai.attacker.example/v1", "http://api.sarvam.ai/v1"]:
        config = SarvamConfig.load({"LLM_API_KEY": KEY, "LLM_BASE_URL": base}.get)
        assert not config.configured


def test_conversation_model_uses_its_supported_endpoint():
    config = SarvamConfig.load({"SARVAM_API_KEY": KEY, "SARVAM_MODEL": "sarvam-105b-conversations"}.get)
    assert config.model == "sarvam-105b-conversations" and config.base_url.endswith("/v1")
    assert not SarvamConfig.load({"SARVAM_API_KEY": KEY, "SARVAM_MODEL": "unavailable-model"}.get).configured


def clean_env(monkeypatch):
    for name in ("SARVAM_API_KEY", "SARVAM_MODEL", "LLM_API_KEY", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("configured", [False, True])
def test_sample_preview_never_spends_credits_and_no_provider_picker(monkeypatch, configured):
    clean_env(monkeypatch)
    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: pytest.fail("preview must be offline"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
    if configured:
        app.secrets["SARVAM_API_KEY"] = KEY
    app.run()
    assert not app.exception and not app.selectbox
    assert [e.label for e in app.text_input] == ["Show title"]
    assert next(b for b in app.button if b.label == "Find promos with AI").disabled
    next(b for b in app.button if b.label == "Preview sample report").click().run()
    assert not app.exception
    assert app.session_state["result"].model == "rules"
    assert app.session_state["usage_ledger"].total("calls") == 0
    assert any("offline preview" in e.value for e in app.info)


def test_snapshot_and_live_run_are_accounted_once_across_rerenders(monkeypatch):
    clean_env(monkeypatch)
    sent = []
    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: sent.append(1) or response())
    monkeypatch.setattr("promo_finder.llm.time.sleep", lambda _: None)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25)
    app.secrets["LLM_API_KEY"] = KEY
    app.secrets["LLM_BASE_URL"] = "https://api.sarvam.ai/v2"
    app.run()
    app.number_input[0].set_value(10.0)
    next(b for b in app.button if b.label == "Save balance snapshot").click().run()
    assert app.session_state["usage_ledger"].remaining == 10
    app.get("file_uploader")[0].upload("demo.zip", DEMO.read_bytes(), "application/zip").run()
    next(b for b in app.button if b.label == "Find promos with AI").click().run()
    assert not app.exception and sent
    ledger = app.session_state["usage_ledger"]
    spend = ledger.spend
    assert ledger.remaining == Decimal(10) - spend
    request_count = len(sent)
    app.run()
    assert not app.exception and len(sent) == request_count
    assert app.session_state["usage_ledger"].spend == spend
    # Replacing a server key starts a separate ledger; never mix two accounts' balances.
    app.secrets["LLM_API_KEY"] = "different-test-account"
    app.run()
    assert app.session_state["usage_ledger"].remaining is None
    assert app.session_state["usage_ledger"].spend == 0


def test_startup_configuration_error_is_handled_without_a_redacted_traceback(monkeypatch):
    clean_env(monkeypatch)
    def stale_backend(*args, **kwargs):
        raise ValueError("Unknown model provider sarvam " + KEY)
    monkeypatch.setattr("promo_finder.llm.Judge", stale_backend)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
    app.secrets["SARVAM_API_KEY"] = KEY
    app.run()
    app.get("file_uploader")[0].upload("demo.zip", DEMO.read_bytes(), "application/zip").run()
    next(b for b in app.button if b.label == "Find promos with AI").click().run()
    assert not app.exception
    assert any("Reboot app" in e.value for e in app.error)
    assert all(KEY not in e.value for e in app.error)


def test_exhausted_credits_are_visible_in_the_report_and_wallet(monkeypatch):
    clean_env(monkeypatch)
    sent = []
    monkeypatch.setattr("promo_finder.llm.requests.post", lambda *a, **k: sent.append(1) or response(status=402))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
    app.secrets["SARVAM_API_KEY"] = KEY
    app.run()
    app.get("file_uploader")[0].upload("demo.zip", DEMO.read_bytes(), "application/zip").run()
    next(b for b in app.button if b.label == "Find promos with AI").click().run()
    assert not app.exception and len(sent) == 1
    assert app.session_state["usage_ledger"].last_error_code == 402
    assert any("out of credits" in e.value for e in app.warning)
    assert app.session_state["result"].model == "rules"
