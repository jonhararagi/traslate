from __future__ import annotations

import fitz
import pytest
import zipfile
from io import BytesIO
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
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
    assert "source_path" not in books[0]

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
    assert "Editar" in response.text
    assert "Eliminar" in response.text
    assert "Exportar EPUB" in response.text



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



def test_import_epub_preserves_original_text_and_chapter_title(client, tmp_path):
    book_file = epub.EpubBook()
    book_file.set_identifier("noveltrad-test")
    book_file.set_title("Test Novel")
    book_file.set_language("en")
    chapter = epub.EpubHtml(title="Chapter One", file_name="chapter01.xhtml", lang="en")
    chapter.content = (
        "<html><head><title>Chapter One</title></head><body>"
        "<h1>Chapter One</h1><p>Oknodie reached level 10.</p>"
        "</body></html>"
    )
    book_file.add_item(chapter)
    book_file.add_item(epub.EpubNcx())
    book_file.add_item(epub.EpubNav())
    book_file.spine = ["nav", chapter]
    epub_path = tmp_path / "sample.epub"
    epub.write_epub(str(epub_path), book_file)

    response = client.post(
        "/api/books/import",
        files={"file": ("sample.epub", epub_path.read_bytes(), "application/epub+zip")},
    )
    assert response.status_code == 200, response.text
    imported = response.json()
    assert imported["format"] == "epub"
    assert imported["title"] == "sample"

    chapters = client.get(f"/api/books/{imported['id']}/chapters").json()
    assert len(chapters) == 1
    assert chapters[0]["title"] == "Chapter One"
    assert "Oknodie reached level 10." in chapters[0]["original_text"]



def test_epub_sections_follow_spine_reading_order(client, tmp_path):
    book_file = epub.EpubBook()
    book_file.set_identifier("noveltrad-order-test")
    book_file.set_title("Reading Order")
    book_file.set_language("en")
    first = epub.EpubHtml(title="First", file_name="first.xhtml", lang="en")
    first.content = "<html><body><h1>First</h1><p>First section text.</p></body></html>"
    second = epub.EpubHtml(title="Second", file_name="second.xhtml", lang="en")
    second.content = "<html><body><h1>Second</h1><p>Second section text.</p></body></html>"
    book_file.add_item(first)
    book_file.add_item(second)
    book_file.add_item(epub.EpubNcx())
    book_file.add_item(epub.EpubNav())
    book_file.spine = ["nav", second, first]
    epub_path = tmp_path / "reading-order.epub"
    epub.write_epub(str(epub_path), book_file)

    response = client.post(
        "/api/books/import",
        files={"file": ("reading-order.epub", epub_path.read_bytes(), "application/epub+zip")},
    )
    assert response.status_code == 200, response.text
    chapters = client.get(f"/api/books/{response.json()['id']}/chapters").json()
    assert [chapter["title"] for chapter in chapters] == ["Second", "First"]



def test_glossary_trims_fields_and_rejects_duplicate_source_terms(client):
    imported = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    ).json()
    endpoint = f"/api/books/{imported['id']}/glossary"
    first = client.post(
        endpoint,
        json={
            "source_term": "  Oknodie  ",
            "preferred_term": " Oknodie ",
            "rule": "protect",
            "notes": "  Nombre propio  ",
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["source_term"] == "Oknodie"
    assert first.json()["preferred_term"] == "Oknodie"
    assert first.json()["notes"] == "Nombre propio"

    duplicate = client.post(
        endpoint,
        json={
            "source_term": "okNODIE",
            "preferred_term": "Ok no muere",
            "rule": "translate",
        },
    )
    assert duplicate.status_code == 409
    assert "ya existe" in duplicate.json()["detail"]


def test_glossary_rejects_whitespace_only_terms(client):
    imported = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    ).json()
    response = client.post(
        f"/api/books/{imported['id']}/glossary",
        json={
            "source_term": "   ",
            "preferred_term": "Oknodie",
            "rule": "protect",
        },
    )
    assert response.status_code == 422



def test_glossary_entry_can_be_edited_and_deleted_only_within_its_book(client):
    first_book = client.post(
        "/api/books/import",
        files={"file": ("first.pdf", pdf_bytes(), "application/pdf")},
    ).json()
    second_book = client.post(
        "/api/books/import",
        files={"file": ("second.pdf", pdf_bytes(), "application/pdf")},
    ).json()
    entry = client.post(
        f"/api/books/{first_book['id']}/glossary",
        json={"source_term": "level", "preferred_term": "nivel", "rule": "translate"},
    ).json()
    entry_id = entry["id"]

    updated = client.put(
        f"/api/books/{first_book['id']}/glossary/{entry_id}",
        json={
            "source_term": "level",
            "preferred_term": "level",
            "rule": "preserve",
            "notes": "Término del sistema; conservar en esta novela.",
            "approved": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["rule"] == "preserve"
    assert updated.json()["approved"] is True

    cross_book_delete = client.delete(f"/api/books/{second_book['id']}/glossary/{entry_id}")
    assert cross_book_delete.status_code == 404
    assert any(x["id"] == entry_id for x in client.get(f"/api/books/{first_book['id']}/glossary").json())

    deleted = client.delete(f"/api/books/{first_book['id']}/glossary/{entry_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert not any(x["id"] == entry_id for x in client.get(f"/api/books/{first_book['id']}/glossary").json())



def test_epub_export_requires_all_chapters_to_be_translated(client):
    imported = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes(), "application/pdf")},
    ).json()
    response = client.get(f"/api/books/{imported['id']}/export/epub")
    assert response.status_code == 409
    assert "sin traducir" in response.json()["detail"]


def test_epub_export_contains_only_saved_spanish_translation_and_escapes_markup(client, tmp_path):
    imported = client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", pdf_bytes("Chapter One\nOriginal source text."), "application/pdf")},
    ).json()
    chapter = client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    translated = "Oknodie & <nivel 10>."
    saved = client.put(
        f"/api/chapters/{chapter['id']}/translation",
        json={"translated_text": translated},
    )
    assert saved.status_code == 200

    response = client.get(f"/api/books/{imported['id']}/export/epub")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/epub+zip")
    assert "attachment;" in response.headers["content-disposition"]

    exported_path = tmp_path / "translated.epub"
    exported_path.write_bytes(response.content)
    exported = epub.read_epub(str(exported_path))
    docs = [item for item in exported.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
    exported_text = "\n".join(BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True) for item in docs)
    assert "Oknodie & <nivel 10>." in exported_text
    assert "Original source text." not in exported_text


def test_import_rejects_fake_pdf_and_malformed_epub(client):
    fake_pdf = client.post(
        "/api/books/import",
        files={"file": ("fake.pdf", b"this is not a PDF", "application/pdf")},
    )
    assert fake_pdf.status_code == 415
    assert "cabecera PDF" in fake_pdf.json()["detail"]

    malformed_epub = client.post(
        "/api/books/import",
        files={"file": ("fake.epub", b"not a ZIP archive", "application/epub+zip")},
    )
    assert malformed_epub.status_code == 422
    assert "EPUB" in malformed_epub.json()["detail"]
    assert client.get("/api/books").json() == []


def test_import_rejects_zip_that_is_not_structurally_an_epub(client):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "not an EPUB package")
    response = client.post(
        "/api/books/import",
        files={"file": ("fake.epub", buffer.getvalue(), "application/epub+zip")},
    )
    assert response.status_code == 422
    assert "estructura obligatoria" in response.json()["detail"]


def test_database_backup_and_restore_preserve_library_and_create_safety_copy(client):
    first = client.post(
        "/api/books/import",
        files={"file": ("first.pdf", pdf_bytes("First novel"), "application/pdf")},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]
    backup = client.post("/api/backups")
    assert backup.status_code == 200, backup.text
    backup_name = backup.json()["name"]
    assert backup_name.startswith("noveltrad-")
    assert backup.json()["size_bytes"] > 0

    second = client.post(
        "/api/books/import",
        files={"file": ("second.pdf", pdf_bytes("Second novel"), "application/pdf")},
    )
    assert second.status_code == 200
    assert len(client.get("/api/books").json()) == 2

    restored = client.post(f"/api/backups/{backup_name}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] is True
    assert restored.json()["safety_backup"] != backup_name
    books = client.get("/api/books").json()
    assert len(books) == 1
    assert books[0]["id"] == first_id

    listed = client.get("/api/backups")
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()}
    assert backup_name in names
    assert restored.json()["safety_backup"] in names


def test_restore_rejects_path_traversal_and_unknown_backup(client):
    traversal = client.post("/api/backups/..%2Fnoveltrad.sqlite3/restore")
    assert traversal.status_code in {400, 404}
    unknown = client.post("/api/backups/noveltrad-20261015T000000Z-deadbeef.sqlite3/restore")
    assert unknown.status_code == 404


def test_restore_rejects_corrupt_backup_without_changing_active_library(client, tmp_path, monkeypatch):
    imported = client.post(
        "/api/books/import",
        files={"file": ("kept.pdf", pdf_bytes("Keep this book"), "application/pdf")},
    ).json()
    backup = client.post("/api/backups").json()
    data_root = tmp_path / "noveltrad-data"
    (data_root / "backups" / backup["name"]).write_bytes(b"not sqlite")

    restored = client.post(f"/api/backups/{backup['name']}/restore")
    assert restored.status_code == 422
    books = client.get("/api/books").json()
    assert [book["id"] for book in books] == [imported["id"]]
