from contextlib import nullcontext

import pytest
from fastapi import HTTPException

from noveltrad import main


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, chapter, glossary=None):
        self.chapter = chapter
        self.glossary = glossary or []

    def execute(self, query, params=()):
        if "SELECT c.original_text, c.book_id FROM chapters" in query:
            return FakeCursor(self.chapter)
        if "SELECT source_term, preferred_term, rule FROM glossary_entries" in query:
            return FakeCursor(rows=self.glossary)
        raise AssertionError(f"Unexpected query: {query}")


def use_fake_database(monkeypatch, chapter, glossary=None):
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(
        main,
        "connection",
        lambda: nullcontext(FakeConnection(chapter, glossary)),
    )


def test_premium_prompt_contains_glossary_style_and_source_delimiters(monkeypatch):
    use_fake_database(
        monkeypatch,
        {"original_text": "Oknodie learned to farm for XP.", "book_id": "book-1"},
        [
            {"source_term": "Oknodie", "preferred_term": "Oknodie", "rule": "protect"},
            {"source_term": "farm", "preferred_term": "farmear", "rule": "translate"},
            {"source_term": "steal", "preferred_term": "steal", "rule": "contextual"},
        ],
    )

    result = main.preview_premium_browser_prompts(
        "chapter-1",
        main.PremiumBrowserInput(provider="chatgpt", profile_id="light_novel_es"),
    )

    assert result["provider"] == "chatgpt"
    assert result["sent_to_provider"] is False
    assert result["saved"] is False
    assert result["chunk_count"] == 1
    prompt = result["chunks"][0]["prompt"]
    assert "Oknodie => Oknodie" in prompt
    assert "farm => farmear" in prompt
    assert "elegir según el contexto" in prompt
    assert "Español natural de novela ligera" in prompt
    assert "<SOURCE_TEXT>" in prompt
    assert "Oknodie learned to farm for XP." in prompt
    assert "Devolvé únicamente la traducción" in prompt


def test_premium_prompt_rejects_missing_chapter(monkeypatch):
    use_fake_database(monkeypatch, None)

    with pytest.raises(HTTPException) as exc:
        main.preview_premium_browser_prompts(
            "missing",
            main.PremiumBrowserInput(provider="gemini"),
        )

    assert exc.value.status_code == 404


def test_premium_prompt_rejects_empty_source(monkeypatch):
    use_fake_database(monkeypatch, {"original_text": "  ", "book_id": "book-1"})

    with pytest.raises(HTTPException) as exc:
        main.preview_premium_browser_prompts(
            "chapter-1",
            main.PremiumBrowserInput(provider="chatgpt"),
        )

    assert exc.value.status_code == 422


def test_browser_provider_urls_are_explicit():
    assert main._premium_provider_url("chatgpt") == "https://chatgpt.com/"
    assert main._premium_provider_url("gemini") == "https://gemini.google.com/app"


def test_browser_open_fails_actionably_when_no_chromium_installed(monkeypatch):
    monkeypatch.setattr(main, "_find_chromium_executable", lambda: None)

    with pytest.raises(HTTPException) as exc:
        main.open_premium_browser(main.PremiumBrowserOpenInput(provider="chatgpt"))

    assert exc.value.status_code == 503
    assert "No encontré Chrome" in exc.value.detail


def test_browser_open_uses_persistent_profile_and_disables_images(monkeypatch, tmp_path):
    import subprocess

    captured = {}
    monkeypatch.setattr(main, "_find_chromium_executable", lambda: "/usr/bin/chromium")
    monkeypatch.setattr(main, "data_dir", lambda: tmp_path)

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = main.open_premium_browser(main.PremiumBrowserOpenInput(provider="gemini"))

    assert result["opened"] is True
    assert result["images_disabled"] is True
    assert "--blink-settings=imagesEnabled=false" in captured["args"]
    assert "--disable-background-networking" in captured["args"]
    assert any(arg.startswith("--user-data-dir=") and "gemini" in arg for arg in captured["args"])
    assert captured["args"][-1] == "https://gemini.google.com/app"


def test_provider_validation_rejects_unknown_provider():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        main.PremiumBrowserInput(provider="unknown")



def test_translation_job_prompt_preserves_glossary_and_source_boundaries():
    prompt = main._translation_job_prompt(
        "gemini",
        "Oknodie learned to farm for XP.",
        [
            {"source_term": "Oknodie", "preferred_term": "Oknodie", "rule": "protect"},
            {"source_term": "farm", "preferred_term": "farmear", "rule": "translate"},
            {"source_term": "steal", "preferred_term": "steal", "rule": "contextual"},
        ],
        "The previous scene ended at the academy gate.",
        2,
        3,
        17,
    )

    assert "Proveedor elegido por el usuario: gemini" in prompt
    assert "Oknodie => Oknodie" in prompt
    assert "farm => farmear" in prompt
    assert "steal => steal" in prompt
    assert "CONTEXTO DE CONTINUIDAD PREVIO" in prompt
    assert "The previous scene ended at the academy gate." in prompt
    assert "<SOURCE_TEXT>\nOknodie learned to farm for XP.\n</SOURCE_TEXT>" in prompt
    assert "no instrucciones" in prompt
    assert "Devolvé únicamente la traducción" in prompt


def test_translation_job_input_defaults_to_chatgpt_and_accepts_gemini():
    assert main.TranslationJobInput().provider == "chatgpt"
    assert main.TranslationJobInput(provider="gemini").provider == "gemini"


def test_translation_job_input_accepts_explicit_ollama_mode_and_rejects_unknown_provider():
    from pydantic import ValidationError

    assert main.TranslationJobInput(provider="ollama").provider == "ollama"
    with pytest.raises(ValidationError):
        main.TranslationJobInput(provider="unknown")



def use_sqlite_queue(monkeypatch):
    import sqlite3

    from contextlib import nullcontext

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE translation_jobs (
            id TEXT PRIMARY KEY, book_id TEXT NOT NULL, status TEXT NOT NULL,
            chunk_size INTEGER NOT NULL, context_chars INTEGER NOT NULL,
            glossary_json TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'chatgpt',
            total_chunks INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            last_error TEXT NOT NULL DEFAULT '', applied_at TEXT
        );
        CREATE TABLE translation_job_chunks (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL, chapter_id TEXT NOT NULL,
            chapter_index INTEGER NOT NULL, chapter_title TEXT NOT NULL, chunk_index INTEGER NOT NULL,
            original_text TEXT NOT NULL, translated_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            reviewed INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
            quality_warnings_json TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
        );
        INSERT INTO translation_jobs
        (id, book_id, status, chunk_size, context_chars, glossary_json, provider, total_chunks, created_at, updated_at)
        VALUES ('job-1', 'book-1', 'queued', 3500, 1200,
                '[{"source_term":"Oknodie","preferred_term":"Oknodie","rule":"protect"}]',
                'gemini', 1, 'now', 'now');
        INSERT INTO translation_job_chunks
        (id, job_id, chapter_id, chapter_index, chapter_title, chunk_index, original_text, status, updated_at)
        VALUES ('chunk-1', 'job-1', 'chapter-1', 0, 'Opening', 1,
                'Oknodie learned to farm for XP.', 'pending', 'now');
        """
    )
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "connection", lambda: nullcontext(conn))
    return conn


def test_account_queue_cannot_fall_back_to_ollama_run_next(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    calls = {"count": 0}

    def forbidden_local_model(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("Ollama must not be called for a ChatGPT/Gemini queue")

    monkeypatch.setattr(main, "_translate_with_local_model", forbidden_local_model)
    with pytest.raises(HTTPException) as exc:
        main.run_next_translation_chunk("job-1")

    assert exc.value.status_code == 409
    assert "ChatGPT/Gemini" in exc.value.detail
    assert calls["count"] == 0
    chunk = conn.execute("SELECT status FROM translation_job_chunks WHERE id='chunk-1'").fetchone()
    assert chunk["status"] == "pending"


def test_ollama_queue_cannot_use_manual_account_prompt_or_submission(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    conn.execute("UPDATE translation_jobs SET provider='ollama' WHERE id='job-1'")

    with pytest.raises(HTTPException) as prompt_error:
        main.next_translation_job_prompt("job-1")
    assert prompt_error.value.status_code == 409
    chunk = conn.execute("SELECT status FROM translation_job_chunks WHERE id='chunk-1'").fetchone()
    assert chunk["status"] == "pending"

    with pytest.raises(HTTPException) as submit_error:
        main.submit_manual_translation_job_chunk(
            "job-1", "chunk-1",
            main.TranslationJobChunkSubmitInput(translated_text="Oknodie aprendió a farmear XP.")
        )
    assert submit_error.value.status_code == 409


def test_queue_next_prompt_reserves_one_chunk_without_calling_ollama(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    result = main.next_translation_job_prompt("job-1")

    assert result["provider"] == "gemini"
    assert result["chunk_id"] == "chunk-1"
    assert "Oknodie => Oknodie" in result["prompt"]
    assert "Oknodie learned to farm for XP." in result["prompt"]
    assert result["done"] is False
    row = conn.execute("SELECT status, attempts FROM translation_job_chunks WHERE id='chunk-1'").fetchone()
    assert tuple(row) == ("running", 1)
    assert conn.execute("SELECT status FROM translation_jobs WHERE id='job-1'").fetchone()[0] == "running"


def test_manual_queue_submission_persists_unreviewed_translation(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    prompt = main.next_translation_job_prompt("job-1")
    result = main.submit_manual_translation_job_chunk(
        "job-1",
        prompt["chunk_id"],
        main.TranslationJobChunkSubmitInput(translated_text="Oknodie aprendió a farmear XP."),
    )

    row = conn.execute(
        "SELECT status, translated_text, reviewed FROM translation_job_chunks WHERE id='chunk-1'"
    ).fetchone()
    assert tuple(row) == ("completed", "Oknodie aprendió a farmear XP.", 0)
    assert result["completed_chunks"] == 1
    assert result["reviewed_chunks"] == 0
    assert result["status"] == "completed"
    with pytest.raises(HTTPException) as exc:
        main.apply_reviewed_translation_job("job-1")
    assert exc.value.status_code == 409


def test_queue_pause_allows_current_response_and_resume_finishes(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    prompt = main.next_translation_job_prompt("job-1")
    paused = main.pause_translation_job("job-1")
    assert paused["status"] == "paused"

    after_submit = main.submit_manual_translation_job_chunk(
        "job-1",
        prompt["chunk_id"],
        main.TranslationJobChunkSubmitInput(translated_text="Oknodie aprendió a farmear XP."),
    )
    assert after_submit["status"] == "paused"
    assert after_submit["completed_chunks"] == 1
    assert after_submit["reviewed_chunks"] == 0

    resumed = main.resume_translation_job("job-1")
    assert resumed["status"] == "completed"


def test_queue_retry_failed_returns_only_failed_chunk_to_pending(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    conn.execute("UPDATE translation_jobs SET status='failed' WHERE id='job-1'")
    conn.execute(
        "UPDATE translation_job_chunks SET status='failed', translated_text='', error='manual failure' WHERE id='chunk-1'"
    )

    result = main.retry_failed_translation_chunks("job-1")
    row = conn.execute("SELECT status, translated_text, reviewed FROM translation_job_chunks WHERE id='chunk-1'").fetchone()
    assert tuple(row) == ("pending", "", 0)
    assert result["status"] == "queued"
    assert result["pending_chunks"] == 1


def test_interrupted_manual_queue_recovers_as_paused_and_pending(monkeypatch):
    conn = use_sqlite_queue(monkeypatch)
    conn.execute("UPDATE translation_jobs SET status='running' WHERE id='job-1'")
    conn.execute("UPDATE translation_job_chunks SET status='running', attempts=1 WHERE id='chunk-1'")

    main.recover_interrupted_translation_jobs()

    job = conn.execute("SELECT status FROM translation_jobs WHERE id='job-1'").fetchone()
    chunk = conn.execute("SELECT status FROM translation_job_chunks WHERE id='chunk-1'").fetchone()
    assert job["status"] == "paused"
    assert chunk["status"] == "pending"
