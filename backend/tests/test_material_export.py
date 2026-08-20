import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_file_import_path import make_client, upload_text


def entries(response):
    return zipfile.ZipFile(io.BytesIO(response.content)).namelist()


def test_batch_export_original_text_and_shared_hash(tmp_path):
    with make_client(tmp_path) as client:
        first = upload_text(client, 'first.txt')
        second = upload_text(client, 'second.txt')
        before = client.get(f"/api/materials/{first['material_id']}").json()
        response = client.post('/api/materials/export', json={'material_ids': [first['material_id'], second['material_id']]})
        assert response.status_code == 200
        names = entries(response)
        assert names == ['originals/first.txt', 'text/first.txt.extracted.txt', 'originals/second.txt', 'text/second.txt.extracted.txt']
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.read('originals/first.txt') == archive.read('originals/second.txt')
            assert archive.read('text/first.txt.extracted.txt').decode() == before['text']
        assert client.get('/api/materials').status_code == 200


def test_batch_export_rejects_deleted_missing_and_invalid(tmp_path):
    with make_client(tmp_path) as client:
        created = upload_text(client, 'deleted.txt')
        assert client.delete(f"/api/materials/{created['material_id']}").status_code == 204
        assert client.post('/api/materials/export', json={'material_ids': [created['material_id']]}).status_code == 404
        assert client.post('/api/materials/export', json={'material_ids': ['missing']}).status_code == 404
        assert client.post('/api/materials/export', json={'material_ids': [], 'include_original': False, 'include_text': False}).status_code == 400
        assert client.post('/api/materials/export', json={'material_ids': [created['material_id']], 'include_original': False, 'include_text': False}).status_code == 400
