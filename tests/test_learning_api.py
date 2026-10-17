from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from noveltrad import main
from noveltrad.learning_store import LEARNING_FILES


def _add_book():
    book_id = str(uuid4())
    chapter_id = str(uuid4())
    with main.connection() as conn:
        conn.execute(
            "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (book_id, "Oknodie test", "epub", "authorized-test.epub", "unused",
             "2026-10-16T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO chapters(id,book_id,chapter_index,title,original_text,translated_text,status) "
            "VALUES(?,?,?,?,?,?,?)",
            (chapter_id, book_id, 0, "Chapter One",
             "Oknodie used the Steal skill to farm for XP.", "", "imported"),
        )
    return book_id


def test_learning_api_requires_literal_source_evidence_and_deduplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id = _add_book()

    with TestClient(main.app) as client:
        payload = {
            "category": "terminology",
            "source": "farm",
            "target": "farmear",
            "decision_type": "contextual-gamer-verb",
            "context": "farm for XP",
            "chapter_index": 0,
            "evidence": "to farm for XP",
            "status": "candidate",
        }
        invalid = client.post(f"/api/books/{book_id}/learning/decisions", json={
            **payload, "evidence": "This phrase does not occur in the original."
        })
        assert invalid.status_code == 422

        first = client.post(f"/api/books/{book_id}/learning/decisions", json=payload)
        assert first.status_code == 200, first.text
        duplicate = client.post(f"/api/books/{book_id}/learning/decisions", json=payload)
        assert duplicate.status_code == 200, duplicate.text
        assert first.json()["created"] is True
        assert duplicate.json()["created"] is False

        learning = client.get(f"/api/books/{book_id}/learning")
        assert learning.status_code == 200
        assert learning.json()["categories"]["terminology"]["total"] == 1

    root = tmp_path / "projects" / book_id
    data = json.loads((root / "aprendizaje" / LEARNING_FILES["terminology"]).read_text())
    assert len(data["entries"]) == 1
    assert len(data["entries"][0]["evidence"]) == 1


def test_learning_candidate_can_be_rejected_but_not_later_promoted(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id = _add_book()
    payload = {
        "category": "terminology",
        "source": "farm",
        "target": "farmear",
        "decision_type": "contextual-gamer-verb",
        "context": "farm for XP",
        "chapter_index": 0,
        "evidence": "to farm for XP",
        "status": "candidate",
    }

    with TestClient(main.app) as client:
        created = client.post(f"/api/books/{book_id}/learning/decisions", json=payload)
        assert created.status_code == 200, created.text
        rejected = client.post(f"/api/books/{book_id}/learning/decisions", json={
            **payload, "status": "rejected"
        })
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"
        attempted_promotion = client.post(f"/api/books/{book_id}/learning/decisions", json={
            **payload, "status": "confirmed"
        })
        assert attempted_promotion.status_code == 200, attempted_promotion.text
        assert attempted_promotion.json()["status"] == "rejected"

        summary = client.get(f"/api/books/{book_id}/learning")
        assert summary.status_code == 200, summary.text
        assert summary.json()["categories"]["terminology"]["rejected"] == 1
        assert summary.json()["entries"][0]["status"] == "rejected"


def test_markdown_export_separates_translated_chapters_and_learning(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id = _add_book()
    with main.connection() as conn:
        conn.execute(
            "UPDATE chapters SET translated_text = ?, status = 'translated' WHERE book_id = ?",
            ("Oknodie usó la habilidad Steal para farmear experiencia.", book_id),
        )

    with TestClient(main.app) as client:
        response = client.post(f"/api/books/{book_id}/learning/export-markdown")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["translated_chapters_exported"] == 1
        assert body["chapters_without_translation"] == 0
        assert body["chapter_files"] == ["capitulo-001-chapter-one.md"]

    root = tmp_path / "projects" / book_id
    translated_file = root / "traduccion" / "capitulo-001-chapter-one.md"
    assert "Oknodie usó la habilidad Steal" in translated_file.read_text(encoding="utf-8")
    assert not (root / "aprendizaje" / translated_file.name).exists()
    assert (root / "aprendizaje" / "README.md").is_file()


def test_learning_api_returns_not_found_for_unknown_book(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    with TestClient(main.app) as client:
        response = client.get("/api/books/does-not-exist/learning")
    assert response.status_code == 404


def test_confirmed_learning_is_reused_in_next_manual_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id = _add_book()

    with TestClient(main.app) as client:
        decision = client.post(f"/api/books/{book_id}/learning/decisions", json={
            "category": "terminology",
            "source": "farm",
            "target": "farmear",
            "decision_type": "contextual-gamer-verb",
            "context": "resource or XP grinding",
            "chapter_index": 0,
            "evidence": "to farm for XP",
            "status": "confirmed",
        })
        assert decision.status_code == 200, decision.text

        job = client.post(f"/api/books/{book_id}/translation-jobs", json={
            "chunk_size": 1000, "context_chars": 0, "provider": "chatgpt",
        })
        assert job.status_code == 200, job.text
        prompt = client.post(
            f"/api/translation-jobs/{job.json()['id']}/next-prompt",
            json={"translation_style": "gamer_terms"},
        )
        assert prompt.status_code == 200, prompt.text
        prompt_text = prompt.json()["prompt"]
        assert "DECISIONES DE TRADUCCIÓN CONFIRMADAS POR CAPÍTULOS ANTERIORES" in prompt_text
        assert "farm => farmear [contextual-gamer-verb]" in prompt_text
        assert "resource or XP grinding" in prompt_text


def test_confirmed_learning_is_reused_in_page_premium_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id = _add_book()
    with main.connection() as conn:
        chapter = conn.execute(
            "SELECT id FROM chapters WHERE book_id = ?", (book_id,)
        ).fetchone()
    assert chapter is not None

    with TestClient(main.app) as client:
        decision = client.post(f"/api/books/{book_id}/learning/decisions", json={
            "category": "terminology",
            "source": "farm",
            "target": "farmear",
            "decision_type": "contextual-gamer-verb",
            "context": "resource or XP grinding",
            "chapter_index": 0,
            "evidence": "to farm for XP",
            "status": "confirmed",
        })
        assert decision.status_code == 200, decision.text

        response = client.post(
            f"/api/chapters/{chapter['id']}/premium-browser-prompts/chunked",
            json={"provider": "chatgpt", "profile_id": "light_novel_es", "chunk_size": 3500, "context_chars": 1200},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["sent_to_provider"] is False
        prompt = result["chunks"][0]["prompt"]
        assert "DECISIONES DE TRADUCCIÓN CONFIRMADAS POR CAPÍTULOS ANTERIORES" in prompt
        assert "farm => farmear [contextual-gamer-verb]" in prompt
        assert "resource or XP grinding" in prompt


def test_downloadable_zip_contains_separate_translation_and_learning_folders(monkeypatch, tmp_path):
    import io
    import zipfile

    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id = _add_book()
    with main.connection() as conn:
        conn.execute(
            "UPDATE chapters SET translated_text = ?, status = 'translated' WHERE book_id = ?",
            ("Oknodie usó Steal.", book_id),
        )

    with TestClient(main.app) as client:
        response = client.get(f"/api/books/{book_id}/learning/export.zip")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/zip")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
        assert "traduccion/capitulo-001-chapter-one.md" in names
        assert "aprendizaje/README.md" in names
        assert {
            f"aprendizaje/{filename}" for filename in LEARNING_FILES.values()
        }.issubset(names)
