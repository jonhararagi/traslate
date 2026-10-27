from fastapi.testclient import TestClient

from noveltrad.main import app


def test_reader_exposes_local_translation_memory_import_and_review(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-ui-data"))
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'id="translation-memory-open"' in html
    assert 'id="translation-memory-file"' in html
    assert 'id="translation-memory-import"' in html
    assert 'id="translation-memory-preview"' in html
    assert 'id="translation-memory-apply"' in html
    assert "Pasar propuesta al editor sin guardar" in html
    assert "no sobrescriben ni guardan la traducción actual" in html

    assert 'id="translation-memory-pages-panel"' in html
    assert 'id="translation-memory-page-source"' in html
    assert 'id="translation-memory-page-target"' in html
    assert 'id="translation-memory-page-approve"' in html
    assert 'id="translation-memory-page-reject"' in html
    assert "Aprobar página revisada" in html
    assert "Solo una página que hayas revisado puede aprobarse" in html
