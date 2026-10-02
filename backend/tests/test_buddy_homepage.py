from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import AppConfig
from app.main import create_app


def test_homepage_aliases_enter_buddy_and_keep_direct_pages(tmp_path):
    config=AppConfig(data_root=tmp_path,auto_detect_enabled=False)
    with TestClient(create_app(config)) as client:
        for suffix in ['', '?next=https://example.invalid', '?view=parent']:
            response=client.get('/'+suffix,follow_redirects=False)
            assert response.status_code==302
            assert response.headers['location']=='/app/buddy.html'
        assert client.get('/app',follow_redirects=False).headers['location'].endswith('/app/')
        for alias in ['/app/','/app/index.html']:
            response=client.get(alias)
            assert response.status_code==200
            assert "location.replace('/app/buddy.html')" in response.text
            assert 'url=/app/buddy.html' in response.text
        for name in ['buddy','student','parent','today','advanced']:
            assert client.get(f'/app/{name}.html').status_code==200
        assert client.get('/legacy').status_code==200
