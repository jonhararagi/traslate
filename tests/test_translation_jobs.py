from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from fastapi import HTTPException

from noveltrad import main


def add_book(chapter_sources: list[tuple[str, str]], *, title: str = "Queue test novel"):
    book_id = str(uuid4())
    with main.connection() as conn:
        conn.execute(
            "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) VALUES(?,?,?,?,?,?)",
            (book_id, title, "epub", "queue-test.epub", "unused", "2026-01-01T00:00:00+00:00"),
        )
        chapter_ids = []
        for index, (title_text, source_text) in enumerate(chapter_sources):
            chapter_id = str(uuid4())
            chapter_ids.append(chapter_id)
            conn.execute(
                "INSERT INTO chapters(id,book_id,chapter_index,title,original_text,translated_text,status) "
                "VALUES(?,?,?,?,?,?,?)",
                (chapter_id, book_id, index, title_text, source_text, "", "imported"),
            )
    return book_id, chapter_ids


def test_book_queue_is_persistent_reviewable_and_never_changes_original(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    first_source = ("Oknodie starts farming and gaining levels. " * 65).strip()
    second_source = "She uses Steal skill. The tsundere rival watches."
    book_id, chapter_ids = add_book([
        ("Chapter 1", first_source),
        ("Chapter 2", second_source),
    ])
    contexts: list[str] = []

    def fake_translate(text, glossary, continuity_context=""):
        contexts.append(continuity_context)
        return "ES: " + text

    monkeypatch.setattr(main, "_translate_with_local_model", fake_translate)
    with TestClient(main.app) as client:
        created = client.post(
            f"/api/books/{book_id}/translation-jobs",
            json={"chunk_size": 1000, "context_chars": 50},
        )
        assert created.status_code == 200, created.text
        job = created.json()
        job_id = job["id"]
        first_chunk_id = job["chunks"][0]["id"]
        first_original = client.get(f"/api/translation-jobs/{job_id}/chunks/{first_chunk_id}").json()["original_text"]
        assert job["status"] == "queued"
        assert job["total_chunks"] > 2
        assert all(chunk["status"] == "pending" for chunk in job["chunks"])

        # A second queue cannot accidentally duplicate work for the same book.
        duplicate = client.post(
            f"/api/books/{book_id}/translation-jobs",
            json={"chunk_size": 1000, "context_chars": 50},
        )
        assert duplicate.status_code == 409

        # Every call commits one chunk; stopping the loop is equivalent to closing the app.
        while job["status"] != "completed":
            response = client.post(f"/api/translation-jobs/{job_id}/run-next")
            assert response.status_code == 200, response.text
            job = response.json()

        assert job["completed_chunks"] == job["total_chunks"]
        assert contexts[0] == ""
        assert contexts[1] == ("ES: " + first_original)[-50:]
        assert len(contexts) == job["total_chunks"]

        # Translation is complete but still not written to chapters until explicitly applied.
        with main.connection() as conn:
            rows = conn.execute(
                "SELECT id, original_text, translated_text, status FROM chapters WHERE book_id = ? ORDER BY chapter_index",
                (book_id,),
            ).fetchall()
        assert rows[0]["original_text"] == first_source
        assert rows[0]["translated_text"] == ""
        assert rows[0]["status"] == "imported"
        assert rows[1]["original_text"] == second_source
        assert rows[1]["translated_text"] == ""

        blocked = client.post(f"/api/translation-jobs/{job_id}/apply")
        assert blocked.status_code == 409
        assert "Revisa y guarda cada fragmento" in blocked.json()["detail"]

        # Explicit review is durable and is required for every fragment.
        state = client.get(f"/api/translation-jobs/{job_id}").json()
        for item in state["chunks"]:
            detail = client.get(f"/api/translation-jobs/{job_id}/chunks/{item['id']}")
            assert detail.status_code == 200
            chunk = detail.json()
            saved_review = client.put(
                f"/api/translation-jobs/{job_id}/chunks/{item['id']}",
                json={"translated_text": chunk["translated_text"]},
            )
            assert saved_review.status_code == 200, saved_review.text

        reviewed_state = client.get(f"/api/translation-jobs/{job_id}").json()
        assert reviewed_state["reviewed_chunks"] == reviewed_state["total_chunks"]
        applied = client.post(f"/api/translation-jobs/{job_id}/apply")
        assert applied.status_code == 200, applied.text
        assert applied.json()["saved"] is True
        assert applied.json()["chapter_count"] == 2

        with main.connection() as conn:
            saved = conn.execute(
                "SELECT id, original_text, translated_text, status FROM chapters WHERE book_id = ? ORDER BY chapter_index",
                (book_id,),
            ).fetchall()
        assert saved[0]["original_text"] == first_source
        assert saved[1]["original_text"] == second_source
        assert saved[0]["translated_text"].startswith("ES: ")
        assert saved[1]["translated_text"].startswith("ES: ")
        assert saved[0]["status"] == "translated"
        final_job = client.get(f"/api/translation-jobs/{job_id}").json()
        assert final_job["status"] == "applied"


def test_failed_chunk_is_recorded_and_can_be_retried_without_losing_completed_chunks(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    source = ("First sentence. " * 80).strip()
    book_id, _ = add_book([("Chapter 1", source)])
    calls = {"count": 0}

    def sometimes_fails(text, glossary, continuity_context=""):
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPException(status_code=502, detail="Ollama temporalmente no disponible.")
        return "ES: " + text

    monkeypatch.setattr(main, "_translate_with_local_model", sometimes_fails)
    with TestClient(main.app) as client:
        created = client.post(
            f"/api/books/{book_id}/translation-jobs",
            json={"chunk_size": 1000, "context_chars": 80},
        )
        assert created.status_code == 200, created.text
        job_id = created.json()["id"]
        failed = client.post(f"/api/translation-jobs/{job_id}/run-next")
        assert failed.status_code == 502
        state = client.get(f"/api/translation-jobs/{job_id}").json()
        assert state["status"] == "failed"
        assert state["failed_chunks"] == 1
        assert state["chunks"][0]["status"] == "failed"
        assert "Ollama temporalmente" in state["last_error"]

        retried = client.post(f"/api/translation-jobs/{job_id}/retry-failed")
        assert retried.status_code == 200
        assert retried.json()["failed_chunks"] == 0
        assert retried.json()["chunks"][0]["status"] == "pending"

        resumed = client.post(f"/api/translation-jobs/{job_id}/run-next")
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "completed"
        assert resumed.json()["completed_chunks"] == 1

        with main.connection() as conn:
            row = conn.execute(
                "SELECT original_text, translated_text FROM chapters WHERE book_id = ?", (book_id,)
            ).fetchone()
        assert row["original_text"] == source
        assert row["translated_text"] == ""


def test_interrupted_running_work_is_recovered_as_paused_and_pending(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id, _ = add_book([("Chapter 1", "One short sentence.")])
    with TestClient(main.app) as client:
        created = client.post(f"/api/books/{book_id}/translation-jobs", json={})
        assert created.status_code == 200
        job_id = created.json()["id"]
        chunk_id = created.json()["chunks"][0]["id"]
        with main.connection() as conn:
            conn.execute("UPDATE translation_jobs SET status = 'running' WHERE id = ?", (job_id,))
            conn.execute("UPDATE translation_job_chunks SET status = 'running' WHERE id = ?", (chunk_id,))

        main.recover_interrupted_translation_jobs()
        state = client.get(f"/api/translation-jobs/{job_id}").json()
        assert state["status"] == "paused"
        assert state["pending_chunks"] == 1
        detail = client.get(f"/api/translation-jobs/{job_id}/chunks/{chunk_id}").json()
        assert detail["status"] == "pending"
        assert "cerró durante este fragmento" in detail["error"]
