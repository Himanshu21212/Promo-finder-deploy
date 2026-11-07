"""Server configuration and the minimal editor workflow, including honest failure states."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from promo_finder.usage import SarvamConfig
from test_sarvam import KEY, response

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'samples' / 'demo_show.zip'


def clean_env(monkeypatch):
    for name in ('SARVAM_API_KEY', 'SARVAM_MODEL', 'LLM_API_KEY', 'LLM_BASE_URL'):
        monkeypatch.delenv(name, raising=False)


def test_legacy_sarvam_credentials_work_without_exposing_configuration():
    config = SarvamConfig.load({'LLM_API_KEY': KEY, 'LLM_BASE_URL': 'https://api.sarvam.ai/v1/'}.get)
    assert config.configured and config.base_url == 'https://api.sarvam.ai/v1'
    assert KEY not in repr(config)


def test_other_provider_keys_are_not_treated_as_sarvam():
    for base in ['https://api.other.example/v1', 'https://api.sarvam.ai.attacker.example/v1', 'http://api.sarvam.ai/v1']:
        config = SarvamConfig.load({'LLM_API_KEY': KEY, 'LLM_BASE_URL': base}.get)
        assert not config.configured


def test_conversation_model_uses_its_supported_endpoint():
    config = SarvamConfig.load({'SARVAM_API_KEY': KEY, 'SARVAM_MODEL': 'sarvam-105b-conversations'}.get)
    assert config.model == 'sarvam-105b-conversations' and config.base_url.endswith('/v1')
    assert not SarvamConfig.load({'SARVAM_API_KEY': KEY, 'SARVAM_MODEL': 'unavailable-model'}.get).configured


@pytest.mark.parametrize('configured', [False, True])
def test_sidebar_contains_only_upload_title_and_find_action(monkeypatch, configured):
    clean_env(monkeypatch)
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda *a, **k: pytest.fail('opening the app must not call AI'))
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    if configured:
        app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    assert not app.exception
    assert [b.label for b in app.sidebar.button] == ['Find promos']
    assert [e.label for e in app.sidebar.text_input] == ['Show title']
    assert len(app.get('file_uploader')) == 2  # main workspace and sidebar share the upload
    assert not app.sidebar.expander and not app.sidebar.number_input and not app.sidebar.selectbox
    assert app.sidebar.button[0].disabled
    assert not app.get('download_button')


def test_uploaded_review_and_rerenders_do_not_repeat_api_calls(monkeypatch):
    clean_env(monkeypatch)
    sent = []
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda *a, **k: sent.append(1) or response())
    monkeypatch.setattr('promo_finder.llm.time.sleep', lambda _: None)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=25)
    app.secrets['LLM_API_KEY'] = KEY
    app.secrets['LLM_BASE_URL'] = 'https://api.sarvam.ai/v2'
    app.run()
    app.get('file_uploader')[0].upload('demo.zip', DEMO.read_bytes(), 'application/zip').run()
    app.sidebar.button[0].click().run()
    assert not app.exception and sent
    assert app.session_state['result'].stats['ai']['judged'] > 0
    assert app.get('download_button')
    request_count = len(sent)
    app.run()
    assert not app.exception and len(sent) == request_count
    assert [b.label for b in app.sidebar.button] == ['Find promos']


def test_startup_configuration_error_is_handled_without_a_redacted_traceback(monkeypatch):
    clean_env(monkeypatch)
    def stale_backend(*args, **kwargs):
        raise ValueError('Unknown model provider sarvam ' + KEY)
    monkeypatch.setattr('promo_finder.llm.Judge', stale_backend)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    app.get('file_uploader')[0].upload('demo.zip', DEMO.read_bytes(), 'application/zip').run()
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert any('currently unavailable' in e.value for e in app.error)
    assert all(KEY not in e.value for e in app.error)


@pytest.mark.parametrize('status', [402, 403])
def test_failed_ai_is_not_presented_as_a_successful_report(monkeypatch, status):
    clean_env(monkeypatch)
    sent = []
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda *a, **k: sent.append(1) or response(status=status))
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    app.get('file_uploader')[0].upload('demo.zip', DEMO.read_bytes(), 'application/zip').run()
    app.sidebar.button[0].click().run()
    assert not app.exception and len(sent) == 1
    assert app.session_state['result'].model == 'rules'
    assert app.error and not app.get('download_button')
    assert any('No AI-ranked report' in caption.value for caption in app.caption)
    backup = next(c for c in app.checkbox if c.label == 'Show backup ranking')
    backup.check().run()
    assert not app.exception and app.get('download_button')
    assert len(sent) == 1  # viewing the backup does not make another paid request
    assert all(KEY not in e.value for e in app.error)


def test_central_upload_and_title_are_synced_without_calling_ai(monkeypatch):
    clean_env(monkeypatch)
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda *a, **k: pytest.fail('uploading must not call AI'))
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
    app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    central = next(w for w in app.get('file_uploader') if w.key.startswith('home_files_'))
    central.upload('My Show-scripts.zip', DEMO.read_bytes(), 'application/zip').run()
    assert not app.exception
    assert app.text_input(key='show_title').value == 'The Maid Was the Heiress'
    assert app.text_input(key='home_title').value == 'The Maid Was the Heiress'
    assert not app.button(key='find_home').disabled and not app.sidebar.button[0].disabled
    app.text_input(key='home_title').set_value('Corrected show').run()
    assert app.text_input(key='show_title').value == 'Corrected show'
    assert 'result' not in app.session_state


def test_new_analysis_clears_report_upload_and_can_review_another_file(monkeypatch):
    clean_env(monkeypatch)
    sent = []
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda *a, **k: sent.append(1) or response())
    monkeypatch.setattr('promo_finder.llm.time.sleep', lambda _: None)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=25)
    app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    central = next(w for w in app.get('file_uploader') if w.key.startswith('home_files_'))
    central.upload('First-scripts.zip', DEMO.read_bytes(), 'application/zip').run()
    app.text_input(key='home_title').set_value('First').run()
    app.button(key='find_home').click().run()
    assert not app.exception and app.session_state['result'].title == 'First'
    requests_before = len(sent)
    app.button(key='new_analysis').click().run()
    assert not app.exception
    for name in ('result', 'compare', 'checks'):
        assert name not in app.session_state
    assert app.session_state['source_files'] == []
    assert app.text_input(key='show_title').value == app.text_input(key='home_title').value == ''
    assert app.button(key='find_home').disabled and not app.get('download_button')
    assert len(sent) == requests_before
    central = next(w for w in app.get('file_uploader') if w.key.startswith('home_files_'))
    central.upload('Second-scripts.zip', DEMO.read_bytes(), 'application/zip').run()
    app.text_input(key='home_title').set_value('Second').run()
    app.button(key='find_home').click().run()
    assert not app.exception and app.session_state['result'].title == 'Second'
    assert len(sent) > requests_before


def test_replacing_scripts_from_sidebar_invalidates_previous_report(monkeypatch):
    clean_env(monkeypatch)
    sent = []
    monkeypatch.setattr('promo_finder.llm.requests.post', lambda *a, **k: sent.append(1) or response())
    monkeypatch.setattr('promo_finder.llm.time.sleep', lambda _: None)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=25)
    app.secrets['SARVAM_API_KEY'] = KEY
    app.run()
    central = next(w for w in app.get('file_uploader') if w.key.startswith('home_files_'))
    central.upload('First-scripts.zip', DEMO.read_bytes(), 'application/zip').run()
    app.button(key='find_home').click().run()
    requests_before = len(sent)
    app.get('file_uploader')[0].upload('Replacement-scripts.zip', DEMO.read_bytes(), 'application/zip').run()
    assert not app.exception and 'result' not in app.session_state
    assert app.text_input(key='home_title').value == 'The Maid Was the Heiress'
    assert [f.name for f in app.session_state['source_files']] == ['Replacement-scripts.zip']
    assert not app.get('download_button') and len(sent) == requests_before
