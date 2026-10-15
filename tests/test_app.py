from __future__ import annotations

import fitz
import pytest
from fastapi.testclient import TestClient

from noveltrad.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-data"))
    with TestClient(app) as test_client:
        yield test_client


def pdf_bytes(text: str = "Chapter One\nOknodie reached level 10.") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(72, 72, 520, 720), text)
    result = document.tobytes()
    document.close()
    return result


def test_health_is_local_first(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "local-first"
    assert response.json()["translation_engine"] == "not-configured"


def test_import_pdf_and_list_chapters(client):
    response = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    book = response.json()
    assert book["format"] == "pdf"
    assert book["chapter_count"] == 1

    books = client.get("/api/books").json()
    assert len(books) == 1
    assert books[0]["title"] == "sample"

    chapters = client.get(f"/api/books/{book['id']}/chapters")
    assert chapters.status_code == 200
    assert "Oknodie" in chapters.json()[0]["original_text"]


def test_only_epub_and_pdf_are_accepted(client):
    response = client.post(
        "/api/books/import",
        files={"file": ("chapter.txt", b"not a supported import", "text/plain")},
    )
    assert response.status_code == 415
    assert "EPUB y PDF" in response.json()["detail"]


def test_glossary_entry_persists_for_book(client):
    imported_response = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    )
    assert imported_response.status_code == 200, imported_response.text
    imported = imported_response.json()
    response = client.post(
        f"/api/books/{imported['id']}/glossary",
        json={
            "source_term": "Oknodie",
            "preferred_term": "Oknodie",
            "rule": "protect",
            "notes": "Nombre propio; no traducir.",
            "approved": True,
        },
    )
    assert response.status_code == 200, response.text
    entries = client.get(f"/api/books/{imported['id']}/glossary").json()
    assert any(entry["source_term"] == "Oknodie" and entry["rule"] == "protect" for entry in entries)


def test_scanned_or_empty_pdf_returns_actionable_error(client):
    document = fitz.open()
    document.new_page()
    raw = document.tobytes()
    document.close()
    response = client.post(
        "/api/books/import",
        files={"file": ("scan.pdf", raw, "application/pdf")},
    )
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"]



def test_reading_progress_persists_and_validates_chapter(client):
    imported_response = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    )
    book = imported_response.json()
    saved = client.put(
        f"/api/books/{book['id']}/progress",
        json={"chapter_index": 0, "scroll_top": 430.5},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"] is True

    listed = client.get("/api/books").json()[0]
    assert '"scroll_top":430.5' in listed["current_location"]

    invalid = client.put(
        f"/api/books/{book['id']}/progress",
        json={"chapter_index": 4, "scroll_top": 0},
    )
    assert invalid.status_code == 422


def test_translation_saves_separate_from_original_and_keeps_versions(client):
    imported_response = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    )
    book = imported_response.json()
    chapter = client.get(f"/api/books/{book['id']}/chapters").json()[0]
    original = chapter["original_text"]

    first = client.put(
        f"/api/chapters/{chapter['id']}/translation",
        json={"translated_text": "Oknodie alcanzó el nivel 10."},
    )
    assert first.status_code == 200, first.text

    second = client.put(
        f"/api/chapters/{chapter['id']}/translation",
        json={"translated_text": "Oknodie llegó al nivel 10."},
    )
    assert second.status_code == 200, second.text

    reread = client.get(f"/api/books/{book['id']}/chapters").json()[0]
    assert reread["original_text"] == original
    assert reread["translated_text"] == "Oknodie llegó al nivel 10."

    versions = client.get(f"/api/chapters/{chapter['id']}/translation/versions")
    assert versions.status_code == 200
    assert [v["translated_text"] for v in versions.json()] == [
        "Oknodie alcanzó el nivel 10.",
        "",
    ]


def test_home_contains_reader_entry_point(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Abrir novela" in response.text
    assert "Traducción" in response.text
    assert "Guardar traducción" in response.text
    assert "Historial" in response.text
    assert "Glosario de esta novela" in response.text
    assert "Proteger nombre/término" in response.text



def test_restore_translation_version_preserves_current_text_in_history(client):
    imported_response = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    )
    book = imported_response.json()
    chapter = client.get(f"/api/books/{book['id']}/chapters").json()[0]
    chapter_id = chapter["id"]

    client.put(
        f"/api/chapters/{chapter_id}/translation",
        json={"translated_text": "Versión A"},
    )
    client.put(
        f"/api/chapters/{chapter_id}/translation",
        json={"translated_text": "Versión B"},
    )

    restored = client.post(f"/api/chapters/{chapter_id}/translation/restore/2")
    assert restored.status_code == 200, restored.text
    assert restored.json()["translated_text"] == "Versión A"

    current = client.get(f"/api/books/{book['id']}/chapters").json()[0]
    assert current["translated_text"] == "Versión A"
    history = client.get(f"/api/chapters/{chapter_id}/translation/versions").json()
    assert history[0]["version_number"] == 3
    assert history[0]["translated_text"] == "Versión B"

    missing = client.post(f"/api/chapters/{chapter_id}/translation/restore/999")
    assert missing.status_code == 404
