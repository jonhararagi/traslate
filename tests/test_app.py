from __future__ import annotations

import fitz
import pytest
import zipfile
from io import BytesIO
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
from fastapi.testclient import TestClient

import noveltrad.main as noveltrad_main
from noveltrad.backup_cli import main as backup_cli_main
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
    assert "Copias de seguridad" in response.text
    assert "Crear copia ahora" in response.text
    assert "Restaurar copia seleccionada" in response.text



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


def test_database_backup_and_restore_preserve_library_and_create_safety_copy(client, tmp_path):
    first = client.post(
        "/api/books/import",
        files={"file": ("first.pdf", pdf_bytes("First novel"), "application/pdf")},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]
    imports_dir = tmp_path / "noveltrad-data" / "imports"
    first_source = next(imports_dir.iterdir())
    first_source_bytes = first_source.read_bytes()
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
    assert restored.json()["source_files_restored"] is True
    assert restored.json()["safety_backup"] != backup_name
    restored_sources = list(imports_dir.iterdir())
    assert len(restored_sources) == 1
    assert restored_sources[0].name == first_source.name
    assert restored_sources[0].read_bytes() == first_source_bytes
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


def test_restore_can_recover_when_active_database_is_corrupt(client, tmp_path):
    imported = client.post(
        "/api/books/import",
        files={"file": ("recover.pdf", pdf_bytes("Recover me"), "application/pdf")},
    ).json()
    backup = client.post("/api/backups").json()
    active_db = tmp_path / "noveltrad-data" / "noveltrad.sqlite3"
    active_db.write_bytes(b"damaged active database bytes")

    restored = client.post(f"/api/backups/{backup['name']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] is True
    assert restored.json()["safety_backup"]
    books = client.get("/api/books").json()
    assert [book["id"] for book in books] == [imported["id"]]


def test_import_rejects_epub_with_excessive_compression_ratio(client):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container/>", compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/chapter.xhtml", "A" * 100_000, compress_type=zipfile.ZIP_DEFLATED)
    response = client.post(
        "/api/books/import",
        files={"file": ("compressed.epub", buffer.getvalue(), "application/epub+zip")},
    )
    assert response.status_code == 422
    assert "compresión segura" in response.json()["detail"]


def test_backup_settings_validate_and_retention_prunes_companion_files(client, tmp_path):
    created = []
    for index in range(3):
        response = client.post(
            "/api/books/import",
            files={"file": (f"novel-{index}.pdf", pdf_bytes(f"Novel {index}"), "application/pdf")},
        )
        assert response.status_code == 200
        backup = client.post("/api/backups")
        assert backup.status_code == 200, backup.text
        created.append(backup.json()["name"])

    settings = client.put(
        "/api/backups/settings",
        json={"enabled": True, "interval_hours": 6, "retention_count": 2},
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["interval_hours"] == 6
    assert settings.json()["retention_count"] == 2
    assert len(settings.json()["removed_backups"]) == 1

    backup_dir = tmp_path / "noveltrad-data" / "backups"
    remaining = {item["name"] for item in client.get("/api/backups").json()}
    assert len(remaining) == 2
    removed = set(created) - remaining
    assert len(removed) == 1
    for name in removed:
        assert not (backup_dir / f"{name.removesuffix('.sqlite3')}-imports").exists()

    invalid_interval = client.put(
        "/api/backups/settings",
        json={"enabled": True, "interval_hours": 0, "retention_count": 2},
    )
    assert invalid_interval.status_code == 422
    invalid_retention = client.put(
        "/api/backups/settings",
        json={"enabled": True, "interval_hours": 6, "retention_count": 101},
    )
    assert invalid_retention.status_code == 422


def test_scheduler_waits_for_interval_then_creates_backup(client, tmp_path):
    settings = client.put(
        "/api/backups/settings",
        json={"enabled": True, "interval_hours": 1, "retention_count": 3},
    )
    assert settings.status_code == 200
    settings_path = tmp_path / "noveltrad-data" / "backup-settings.json"
    saved = __import__("json").loads(settings_path.read_text(encoding="utf-8"))
    saved["schedule_started_at"] = "2020-01-01T00:00:00+00:00"
    settings_path.write_text(__import__("json").dumps(saved), encoding="utf-8")

    due = noveltrad_main.run_scheduled_backup_if_due()
    assert due["status"] == "created"
    assert due["created"]
    saved_after = noveltrad_main.load_backup_settings()
    assert saved_after["last_success_at"]
    not_due = noveltrad_main.run_scheduled_backup_if_due()
    assert not_due["status"] == "not_due"


def test_scheduler_failure_is_recorded_and_retried_without_advancing_schedule(client, tmp_path, monkeypatch):
    settings_path = tmp_path / "noveltrad-data" / "backup-settings.json"
    saved = __import__("json").loads(settings_path.read_text(encoding="utf-8"))
    saved["enabled"] = True
    saved["interval_hours"] = 1
    saved["schedule_started_at"] = "2020-01-01T00:00:00+00:00"
    saved["last_success_at"] = None
    settings_path.write_text(__import__("json").dumps(saved), encoding="utf-8")

    def fail_backup():
        raise OSError("simulated disk full")

    monkeypatch.setattr(noveltrad_main, "create_database_backup", fail_backup)
    first = noveltrad_main.run_scheduled_backup_if_due()
    assert first["status"] == "error"
    assert "simulated disk full" in first["error"]
    persisted = noveltrad_main.load_backup_settings()
    assert persisted["last_success_at"] is None
    assert "simulated disk full" in persisted["last_error"]
    second = noveltrad_main.run_scheduled_backup_if_due()
    assert second["status"] == "retry_wait"
    assert second["retry_after_at"] == first["retry_after_at"]
    assert noveltrad_main.load_backup_settings()["failure_count"] == 1

    dt = __import__("datetime")
    retry_time = dt.datetime.fromisoformat(first["retry_after_at"]) + dt.timedelta(seconds=1)
    third = noveltrad_main.run_scheduled_backup_if_due(now=retry_time)
    assert third["status"] == "error"
    assert third["retry_delay_seconds"] == 600
    persisted = noveltrad_main.load_backup_settings()
    assert persisted["failure_count"] == 2
    assert persisted["retry_after_at"] == third["retry_after_at"]


def test_restore_filesystem_failure_rolls_back_imports_and_keeps_live_database(client, tmp_path, monkeypatch):
    imported = client.post(
        "/api/books/import",
        files={"file": ("stable.pdf", pdf_bytes("Stable book"), "application/pdf")},
    ).json()
    backup = client.post("/api/backups").json()
    client.post(
        "/api/books/import",
        files={"file": ("later.pdf", pdf_bytes("Later book"), "application/pdf")},
    )
    imports_dir = tmp_path / "noveltrad-data" / "imports"
    original_sources = {p.name: p.read_bytes() for p in imports_dir.iterdir()}
    real_replace = noveltrad_main.os.replace
    failed = {"value": False}

    def fail_live_db_swap(source, destination):
        if (not failed["value"] and Path(destination) == noveltrad_main.database_path()
                and Path(source).name.startswith("restore-")):
            failed["value"] = True
            raise OSError("simulated disk failure during restore")
        return real_replace(source, destination)

    from pathlib import Path
    monkeypatch.setattr(noveltrad_main.os, "replace", fail_live_db_swap)
    response = client.post(f"/api/backups/{backup['name']}/restore")
    assert response.status_code == 500
    assert failed["value"] is True
    assert len(client.get("/api/books").json()) == 2
    assert {p.name: p.read_bytes() for p in imports_dir.iterdir()} == original_sources
    assert any(book["id"] == imported["id"] for book in client.get("/api/books").json())


def test_backup_preferences_survive_restoring_an_older_library_snapshot(client):
    imported = client.post(
        "/api/books/import",
        files={"file": ("preferences.pdf", pdf_bytes("Preferences remain"), "application/pdf")},
    ).json()
    backup = client.post("/api/backups").json()
    changed = client.put(
        "/api/backups/settings",
        json={"enabled": False, "interval_hours": 8, "retention_count": 7},
    )
    assert changed.status_code == 200

    restored = client.post(f"/api/backups/{backup['name']}/restore")
    assert restored.status_code == 200, restored.text
    settings = client.get("/api/backups/settings").json()
    assert settings["enabled"] is False
    assert settings["interval_hours"] == 8
    assert settings["retention_count"] == 7
    assert [book["id"] for book in client.get("/api/books").json()] == [imported["id"]]



def test_full_library_restore_recovers_glossary_translation_versions_progress_and_originals(client, tmp_path):
    imported = client.post(
        "/api/books/import",
        files={"file": ("full-recovery.pdf", pdf_bytes("Oknodie reached level 10."), "application/pdf")},
    )
    assert imported.status_code == 200, imported.text
    book = imported.json()
    book_id = book["id"]
    chapter = client.get(f"/api/books/{book_id}/chapters").json()[0]
    chapter_id = chapter["id"]

    glossary = client.post(
        f"/api/books/{book_id}/glossary",
        json={
            "source_term": "Oknodie",
            "preferred_term": "Oknodie",
            "rule": "protect",
            "notes": "Nombre propio aprobado",
            "approved": True,
        },
    )
    assert glossary.status_code == 200, glossary.text
    assert client.put(
        f"/api/books/{book_id}/progress",
        json={"chapter_index": 0, "scroll_top": 731.25},
    ).status_code == 200
    assert client.put(
        f"/api/chapters/{chapter_id}/translation",
        json={"translated_text": "Oknodie alcanzó el nivel 10."},
    ).status_code == 200
    assert client.put(
        f"/api/chapters/{chapter_id}/translation",
        json={"translated_text": "Oknodie llegó al nivel 10."},
    ).status_code == 200

    source_dir = tmp_path / "noveltrad-data" / "imports"
    source_before = {path.name: path.read_bytes() for path in source_dir.iterdir()}
    backup = client.post("/api/backups")
    assert backup.status_code == 200, backup.text
    backup_name = backup.json()["name"]

    # Damage every recoverable category after the snapshot: metadata, glossary,
    # current translation, translation history, reading position and imported files.
    assert client.delete(f"/api/books/{book_id}/glossary/{glossary.json()['id']}").status_code in {200, 204}
    assert client.put(
        f"/api/chapters/{chapter_id}/translation",
        json={"translated_text": "Texto posterior que no debe sobrevivir a la restauración."},
    ).status_code == 200
    assert client.put(
        f"/api/books/{book_id}/progress",
        json={"chapter_index": 0, "scroll_top": 12},
    ).status_code == 200
    extra = client.post(
        "/api/books/import",
        files={"file": ("extra-after-snapshot.pdf", pdf_bytes("This is newer"), "application/pdf")},
    )
    assert extra.status_code == 200
    for path in source_dir.iterdir():
        if path.name not in source_before:
            path.unlink()

    restored = client.post(f"/api/backups/{backup_name}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] is True

    books = client.get("/api/books").json()
    assert [item["id"] for item in books] == [book_id]
    assert '"scroll_top":731.25' in books[0]["current_location"]
    chapters = client.get(f"/api/books/{book_id}/chapters").json()
    assert len(chapters) == 1
    assert chapters[0]["original_text"] == "Oknodie reached level 10."
    assert chapters[0]["translated_text"] == "Oknodie llegó al nivel 10."
    versions = client.get(f"/api/chapters/{chapter_id}/translation/versions").json()
    assert [item["translated_text"] for item in versions] == [
        "Oknodie alcanzó el nivel 10.",
        "",
    ]
    glossary_after = client.get(f"/api/books/{book_id}/glossary").json()
    assert any(
        item["source_term"] == "Oknodie"
        and item["preferred_term"] == "Oknodie"
        and bool(item["approved"])
        for item in glossary_after
    )
    source_after = {path.name: path.read_bytes() for path in source_dir.iterdir()}
    assert source_after == source_before


def test_headless_backup_cli_runs_due_backup_without_starting_web_server(client, tmp_path, monkeypatch):
    imported = client.post(
        "/api/books/import",
        files={"file": ("cli.pdf", pdf_bytes("CLI backup"), "application/pdf")},
    )
    assert imported.status_code == 200
    data_root = tmp_path / "noveltrad-data"
    settings_path = data_root / "backup-settings.json"
    settings = noveltrad_main.load_backup_settings()
    settings.update({
        "enabled": True,
        "interval_hours": 1,
        "retention_count": 14,
        "last_success_at": None,
        "schedule_started_at": "2000-01-01T00:00:00+00:00",
        "last_error": None,
    })
    noveltrad_main.save_backup_settings(settings)

    assert backup_cli_main() == 0
    backups = list((data_root / "backups").glob("noveltrad-*.sqlite3"))
    assert backups, "headless CLI should create a due backup"
    assert any(path.is_dir() for path in (data_root / "backups").glob("noveltrad-*-imports"))



def test_headless_backup_cli_does_not_create_an_empty_database(client, tmp_path, monkeypatch):
    empty_home = tmp_path / "empty-noveltrad-home"
    monkeypatch.setenv("NOVELTRAD_HOME", str(empty_home))
    assert backup_cli_main() == 2
    assert not (empty_home / "noveltrad.sqlite3").exists()


def test_scheduler_backoff_resets_after_success(client, tmp_path):
    from datetime import datetime, timezone
    settings_path = tmp_path / "noveltrad-data" / "backup-settings.json"
    saved = __import__("json").loads(settings_path.read_text(encoding="utf-8"))
    saved.update({"enabled": True, "interval_hours": 1, "schedule_started_at": "2020-01-01T00:00:00+00:00", "last_success_at": None, "failure_count": 2, "retry_after_at": "2020-01-01T00:10:00+00:00"})
    settings_path.write_text(__import__("json").dumps(saved), encoding="utf-8")
    result = noveltrad_main.run_scheduled_backup_if_due(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert result["status"] == "created"
    persisted = noveltrad_main.load_backup_settings()
    assert persisted["failure_count"] == 0
    assert persisted["retry_after_at"] is None
    assert persisted["last_error"] is None


def test_concurrent_due_scheduler_calls_create_only_one_backup(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    settings_path = tmp_path / "noveltrad-data" / "backup-settings.json"
    saved = __import__("json").loads(settings_path.read_text(encoding="utf-8"))
    saved.update({"enabled": True, "interval_hours": 1, "schedule_started_at": "2020-01-01T00:00:00+00:00", "last_success_at": None, "retry_after_at": None, "failure_count": 0})
    settings_path.write_text(__import__("json").dumps(saved), encoding="utf-8")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: noveltrad_main.run_scheduled_backup_if_due(now=now), range(4)))
    assert sum(result["status"] == "created" for result in results) == 1
    assert sum(result["status"] == "not_due" for result in results) == 3
    backups = list((tmp_path / "noveltrad-data" / "backups").glob("noveltrad-*.sqlite3"))
    assert len(backups) == 1



def test_backup_lock_serializes_independent_processes(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    import time

    data_home = tmp_path / "noveltrad-cross-process"
    monkeypatch.setenv("NOVELTRAD_HOME", str(data_home))
    script = (
        'import time; from noveltrad.main import _cross_process_backup_lock; '
        'lock = _cross_process_backup_lock(); lock.__enter__(); '
        'print("LOCK_HELD", flush=True); time.sleep(1.0); lock.__exit__(None, None, None)'
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script],
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        while True:
            line = child.stdout.readline()
            assert line, child.stderr.read() if child.stderr else "child exited before acquiring the lock"
            if line.strip() == "LOCK_HELD":
                break
        started = time.monotonic()
        with noveltrad_main._cross_process_backup_lock():
            waited = time.monotonic() - started
        assert waited >= 0.5, f"second process did not wait for the lock (waited {waited:.3f}s)"
        assert child.wait(timeout=5) == 0, child.stderr.read() if child.stderr else ""
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if child.stdout:
            child.stdout.close()
        if child.stderr:
            child.stderr.close()



def test_restore_imports_swap_failure_preserves_live_library_and_sources(client, tmp_path, monkeypatch):
    imported = client.post(
        "/api/books/import",
        files={"file": ("stable-before-swap.pdf", pdf_bytes("Stable before swap"), "application/pdf")},
    ).json()
    backup = client.post("/api/backups").json()
    later = client.post(
        "/api/books/import",
        files={"file": ("later-before-swap.pdf", pdf_bytes("Later before swap"), "application/pdf")},
    ).json()
    data_root = tmp_path / "noveltrad-data"
    imports_dir = data_root / "imports"
    original_sources = {p.name: p.read_bytes() for p in imports_dir.iterdir()}
    real_replace = noveltrad_main.os.replace
    failed = {"value": False}

    def fail_staged_imports_swap(source, destination):
        if (
            not failed["value"]
            and str(destination) == str(imports_dir)
            and str(source).startswith(str(data_root / "restore-imports-"))
        ):
            failed["value"] = True
            raise OSError("simulated failure swapping restored source files")
        return real_replace(source, destination)

    monkeypatch.setattr(noveltrad_main.os, "replace", fail_staged_imports_swap)
    response = client.post(f"/api/backups/{backup['name']}/restore")
    assert response.status_code == 500
    assert failed["value"] is True
    assert {p.name: p.read_bytes() for p in imports_dir.iterdir()} == original_sources
    assert {book["id"] for book in client.get("/api/books").json()} == {imported["id"], later["id"]}


def test_backup_prune_and_restore_operations_are_serialized_together(client, tmp_path, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    first = client.post(
        "/api/books/import",
        files={"file": ("first-concurrent.pdf", pdf_bytes("First concurrent book"), "application/pdf")},
    )
    assert first.status_code == 200, first.text
    stale = client.post("/api/backups")
    assert stale.status_code == 200, stale.text
    # Ensure retention removes the deliberately older snapshot, not the restore target.
    stale_path = tmp_path / "noveltrad-data" / "backups" / stale.json()["name"]
    import os
    os.utime(stale_path, (stale_path.stat().st_atime - 60, stale_path.stat().st_mtime - 60))
    target = client.post("/api/backups")
    assert target.status_code == 200, target.text
    target_name = target.json()["name"]

    second = client.post(
        "/api/books/import",
        files={"file": ("second-concurrent.pdf", pdf_bytes("Second concurrent book"), "application/pdf")},
    )
    assert second.status_code == 200, second.text

    entered_snapshot = threading.Event()
    release_snapshot = threading.Event()
    real_snapshot = noveltrad_main.snapshot_imports_for_backup

    def pause_snapshot(path):
        if threading.current_thread().name.startswith("backup-race"):
            entered_snapshot.set()
            if not release_snapshot.wait(timeout=5):
                raise TimeoutError("test did not release the backup snapshot")
        return real_snapshot(path)

    monkeypatch.setattr(noveltrad_main, "snapshot_imports_for_backup", pause_snapshot)
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="backup-race") as pool:
        backup_future = pool.submit(noveltrad_main.create_database_backup)
        assert entered_snapshot.wait(timeout=5), "backup did not enter its critical section"
        prune_future = pool.submit(noveltrad_main.prune_backups, 2)
        restore_future = pool.submit(noveltrad_main.restore_backup, target_name)
        time.sleep(0.1)
        release_snapshot.set()
        new_backup = backup_future.result(timeout=10)
        removed = prune_future.result(timeout=10)
        restored = restore_future.result(timeout=10)

    assert new_backup.is_file()
    assert stale.json()["name"] in removed
    assert restored["restored"] is True
    assert restored["backup_name"] == target_name
    assert noveltrad_main.validate_database_file(new_backup) is None
    remaining = {item["name"] for item in client.get("/api/backups").json()}
    assert target_name in remaining
    assert new_backup.name in remaining
    assert restored["safety_backup"] in remaining
    assert stale.json()["name"] not in remaining
    # Restore deliberately keeps a safety snapshot, in addition to the target and new backup.
    assert len(remaining) == 3
    for backup_name in remaining:
        assert noveltrad_main.validate_database_file(tmp_path / "noveltrad-data" / "backups" / backup_name) is None
    assert len(client.get("/api/books").json()) == 1
    assert not list((tmp_path / "noveltrad-data").glob("restore-*.sqlite3"))
