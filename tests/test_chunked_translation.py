from __future__ import annotations

import re
from uuid import uuid4

from fastapi.testclient import TestClient

from noveltrad import main


def test_split_translation_chunks_preserves_short_paragraphs():
    source = "Opening paragraph.\\n\\nSecond paragraph with gamer slang."
    chunks = main._split_translation_chunks(source, 100)
    assert chunks == [source]


def test_split_translation_chunks_bounds_long_text_and_preserves_characters():
    source = ("First sentence about Oknodie and her level. " * 18).strip()
    chunks = main._split_translation_chunks(source, 80)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 80 for chunk in chunks)
    # Chunk boundaries may normalize whitespace, but must not omit or reorder source words.
    normalized_source = re.sub(r"\\s+", " ", source).strip()
    normalized_chunks = re.sub(r"\\s+", " ", " ".join(chunks)).strip()
    assert normalized_chunks == normalized_source


def test_chunked_preview_is_sequential_reviewable_and_never_saves(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path))
    main.init_db()
    book_id, chapter_id = str(uuid4()), str(uuid4())
    source = "Oknodie starts farming.\\n\\nHer level rises.\\n\\nShe uses Steal skill."
    with main.connection() as conn:
        conn.execute(
            "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) VALUES(?,?,?,?,?,?)",
            (book_id, "I Became the Academy Villain's Daughter", "epub", "novel.epub", "unused", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO chapters(id,book_id,chapter_index,title,original_text,translated_text,status) VALUES(?,?,?,?,?,?,?)",
            (chapter_id, book_id, 0, "Chapter 1", source, "", "imported"),
        )

    contexts = []

    def fake_translate(text, glossary, continuity_context=""):
        contexts.append(continuity_context)
        return "ES: " + text

    monkeypatch.setattr(main, "_translate_with_local_model", fake_translate)
    with TestClient(main.app) as client:
        response = client.post(
            f"/api/chapters/{chapter_id}/premium-translation-preview/chunked",
            json={"chunk_size": 1000, "context_chars": 50},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["preview_only"] is True
    assert payload["saved"] is False
    assert payload["chunk_count"] == len(payload["chunks"])
    assert [item["index"] for item in payload["chunks"]] == list(range(1, len(payload["chunks"]) + 1))
    assert payload["text"] == "\\n\\n".join(item["translated"] for item in payload["chunks"])
    assert contexts[0] == ""
    if len(contexts) > 1:
        assert contexts[1] == ("ES: " + payload["chunks"][0]["original"])[-50:]
    with main.connection() as conn:
        row = conn.execute("SELECT original_text, translated_text, status FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
    assert row["original_text"] == source
    assert row["translated_text"] == ""
    assert row["status"] == "imported"
