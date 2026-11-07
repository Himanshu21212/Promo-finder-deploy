"""Only factual progress is exposed; pipeline diagnostics never become UI copy."""
from pathlib import Path
import requests
from streamlit.testing.v1 import AppTest

from promo_finder import load_path
from promo_finder.llm import Judge
from promo_finder.pipeline import run
from promo_finder.progress import ReviewProgress
from promo_finder.usage import SarvamConfig
from test_sarvam import KEY, response, RATING

ROOT = Path(__file__).resolve().parents[1]


def test_progress_follows_actual_pipeline_events_without_showing_raw_diagnostics():
    view = ReviewProgress()
    seen = []
    def update(message):
        view.update(message)
        seen.append((message, view.stage, view.html()))
    j = Judge('custom:test', transport=lambda _: RATING, min_interval=0, use_cache=False)
    result = run(load_path(ROOT / 'samples/demo_show.zip'), 'demo', j, progress=update)
    assert result.stats['ai']['judged'] > 0
    assert seen and view.stage == 3
    assert len(view.reviewed) == result.stats['ai']['judged']
    assert view.total == result.stats['ai']['shortlisted']
    assert any(stage == 1 for _, stage, _ in seen)
    assert any('Clip 1 of ' in html for _, _, html in seen)
    for _, _, html in seen:
        for diagnostic in ['Parsed', 'Generated', 'Premise tropes', 'custom:test', 'keeping rules score', 'API request']:
            assert diagnostic not in html


def test_failed_review_is_not_counted_or_presented_as_report_preparation():
    view = ReviewProgress()
    view.update('AI judge sarvam:sarvam-105b: rating 5 shortlisted candidates…')
    view.update('  Reviewing candidate 1/5…')
    view.update('  Candidate 1: review failed (API request timed out); keeping rules score.')
    view.update('  0/5 rated by the model (1 calls, 0 from cache, 1 failed).')
    assert view.stage == 2 and not view.reviewed
    assert 'aria-valuenow="0"' in view.html()
    assert 'API request' not in view.html() and 'failed' not in view.html()
    view.update('  Candidate 2: review complete.')
    view.update('  Candidate 2: review complete.')
    assert len(view.reviewed) == 1  # duplicate updates do not invent more progress


def test_v1_default_and_explicit_v2_are_configured_deliberately():
    assert SarvamConfig.load({'SARVAM_API_KEY': KEY}.get).base_url == 'https://api.sarvam.ai/v1'
    explicit = SarvamConfig.load({'SARVAM_API_KEY': KEY, 'SARVAM_BASE_URL': 'https://api.sarvam.ai/v2'}.get)
    assert explicit.base_url == 'https://api.sarvam.ai/v2'
    legacy = SarvamConfig.load({'LLM_API_KEY': KEY, 'LLM_BASE_URL': 'https://api.sarvam.ai/v2'}.get)
    assert legacy.configured and legacy.base_url == 'https://api.sarvam.ai/v1'
    assert not SarvamConfig.load({'SARVAM_API_KEY': KEY, 'SARVAM_BASE_URL': 'https://elsewhere.example'}.get).configured


def test_v2_does_not_receive_the_v1_only_thinking_switch(monkeypatch):
    sent = []
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda url, **kw: sent.append(kw) or response())
    j = Judge('sarvam:sarvam-105b', api_key=KEY, base_url='https://api.sarvam.ai/v2', use_cache=False)
    j._raw('Return JSON')
    assert 'reasoning_effort' not in sent[0]['json']
    assert sent[0]['json']['max_tokens'] == 768


def test_timeout_becomes_a_clean_error_after_one_request(monkeypatch):
    sent = []
    def timeout(*args, **kwargs):
        sent.append(kwargs)
        raise requests.Timeout()
    monkeypatch.setattr('promo_finder.llm.requests.post', timeout)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    app.get('file_uploader')[0].upload('demo.zip', (ROOT / 'samples/demo_show.zip').read_bytes(), 'application/zip').run()
    app.sidebar.button[0].click().run()
    assert not app.exception and len(sent) == 1
    assert any('took too long' in e.value for e in app.error)
    assert not app.get('status') and not app.get('download_button')
    assert [e.label for e in app.expander] == ['Run details']
