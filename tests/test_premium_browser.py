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
