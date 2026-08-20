import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_file_import_path import make_client, upload_text


def test_pagination_preserves_legacy_arrays_and_returns_pages(tmp_path):
    with make_client(tmp_path) as client:
        created = [upload_text(client, f"page-{i}.txt", f"page body {i}".encode()) for i in range(25)]
        first = client.get('/api/materials?limit=20&offset=0').json()
        second = client.get('/api/materials?limit=20&offset=20').json()
        assert (len(first['items']), first['total'], first['has_more']) == (20, 25, True)
        assert (len(second['items']), second['total'], second['has_more']) == (5, 25, False)
        assert {x['id'] for x in first['items']}.isdisjoint({x['id'] for x in second['items']})
        assert isinstance(client.get('/api/materials').json(), list)
        assert client.get('/api/materials?limit=20&offset=40').json()['items'] == []
        assert client.get('/api/materials?limit=0').status_code == 400
        assert client.get('/api/materials?limit=101').status_code == 400
        assert client.get('/api/materials?offset=-1').status_code == 400
        assert client.get('/api/materials?limit=abc').status_code == 400


def test_search_and_deleted_pagination_keep_safe_items(tmp_path):
    with make_client(tmp_path) as client:
        created = [upload_text(client, f"search-{i}.txt", b"StudyBuddy paginated body") for i in range(5)]
        page = client.get('/api/materials?q=StudyBuddy&limit=2&offset=0').json()
        assert page['total'] == 5 and len(page['items']) == 2
        assert all('snippet' in x and 'match_fields' in x and 'text' not in x and 'stored_path' not in x for x in page['items'])
        for item in created:
            assert client.delete(f"/api/materials/{item['material_id']}").status_code == 204
        deleted = client.get('/api/materials/deleted?limit=2&offset=0').json()
        assert deleted['total'] == 5 and len(deleted['items']) == 2
        assert all('text' not in x and 'stored_path' not in x for x in deleted['items'])
