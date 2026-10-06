"""TTS skill tests: fake audio only, no real SAPI or network Provider."""
import os
import wave
from types import SimpleNamespace
from pathlib import Path

from fastapi.testclient import TestClient

from app.capabilities import resolve_config
from app.config import AppConfig, config_from_environment
from app.main import create_app
from app.tts import SapiTtsProvider


def test_tts_is_disabled_by_default_and_discoverable(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        result = api.get('/api/tts/capabilities')
        assert result.status_code == 200
        assert result.json()['status'] == 'disabled'
        assert api.post('/api/tts/speak', json={'text': 'not enabled'}).status_code == 503


def test_fake_tts_creates_valid_wav_and_cache_hit(tmp_path):
    config = AppConfig(data_root=tmp_path, tts_enabled=True, tts_provider_id='fake')
    with TestClient(create_app(config)) as api:
        first = api.post('/api/tts/speak', json={'text': 'Synthetic knowledge module'}).json()
        cache = tmp_path / 'tts-cache'
        files = list(cache.glob('*.wav'))
        assert first['engine'] == 'fake' and first['fallback_used'] is False
        assert len(files) == 1 and first['audio_url'].startswith('/api/tts/audio/')
        with wave.open(str(files[0]), 'rb') as audio:
            assert audio.getnchannels() == 1 and audio.getframerate() == 8000
        second = api.post('/api/tts/speak', json={'text': 'Synthetic knowledge module'}).json()
        assert len(list(cache.glob('*.wav'))) == 1 and second['audio_url'] != first['audio_url']
        audio = api.get(first['audio_url'])
        assert audio.status_code == 200 and audio.headers['content-type'].startswith('audio/wav')


def test_sapi_provider_passes_output_path_via_environment(monkeypatch, tmp_path):
    seen = {}

    def fake_run(args, **kwargs):
        seen['args'] = args
        seen['env'] = kwargs['env']
        Path(kwargs['env']['STUDYBUDDY_TTS_OUTPUT']).write_bytes(b'RIFF')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr('app.tts.subprocess.run', fake_run)
    output = tmp_path / 'sapi.wav'
    SapiTtsProvider('powershell.exe').synthesize('hello', output, voice=None, rate=1.0,
                                                  timeout_seconds=5)
    assert seen['args'][-1].endswith("$s.SetOutputToWaveFile($env:STUDYBUDDY_TTS_OUTPUT); $s.Speak($text); $s.Dispose()")
    assert str(output) not in seen['args']
    assert seen['env']['STUDYBUDDY_TTS_OUTPUT'] == str(output)
    assert output.is_file()


def test_tts_control_status_retry_and_safe_boundaries(tmp_path):
    config = AppConfig(data_root=tmp_path, tts_enabled=True, tts_provider_id='fake')
    with TestClient(create_app(config)) as api:
        playback = api.post('/api/tts/speak', json={'text': 'Control me'}).json()
        pid = playback['playback_id']
        assert api.post('/api/tts/control', json={'playback_id': pid, 'action': 'pause'}).json()['state'] == 'paused'
        assert api.get('/api/tts/status/' + pid).json()['state'] == 'paused'
        assert api.post('/api/tts/control', json={'playback_id': pid, 'action': 'play'}).json()['state'] == 'playing'
        assert api.post('/api/tts/control', json={'playback_id': pid, 'action': 'stop'}).json()['state'] == 'stopped'
        invalid = api.post('/api/tts/speak', json={'text': 'x' * 12001})
        assert invalid.status_code == 422
        missing = api.get('/api/tts/audio/missing-playback')
        assert missing.status_code == 404 and missing.json() == {'detail': 'tts_playback_not_found'}
        assert all('Control me' not in path.name for path in (tmp_path / 'tts-cache').iterdir())


def test_tts_environment_defaults_remain_off(monkeypatch, tmp_path):
    for name in list(os.environ):
        if name.startswith('STUDYBUDDY_TTS_'):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('STUDYBUDDY_DATA_ROOT', str(tmp_path))
    config = config_from_environment()
    assert config.tts_enabled is False and config.tts_provider_id is None


def test_tts_settings_are_layered_without_exposing_paths(tmp_path):
    base = AppConfig(data_root=tmp_path)
    effective = resolve_config(base, settings={
        'tts_enabled': True, 'tts_provider_id': 'fake',
        'tts_voice': 'synthetic-voice', 'tts_sapi_path': 'C:/private/sapi.exe',
    })
    assert effective.tts_enabled is True and effective.tts_provider_id == 'fake'
    assert effective.tts_voice == 'synthetic-voice'


def test_tts_settings_apply_to_existing_app_without_restart(tmp_path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        saved = api.put('/api/system/settings', json={
            'tts_enabled': True, 'tts_provider_id': 'fake',
        })
        assert saved.status_code == 200
        assert api.post('/api/tts/speak', json={'text': 'settings apply'}).status_code == 200

        cleared = api.post('/api/system/settings/clear', json={
            'keys': ['tts_enabled', 'tts_provider_id'],
        })
        assert cleared.status_code == 200
        assert api.post('/api/tts/speak', json={'text': 'disabled again'}).status_code == 503
