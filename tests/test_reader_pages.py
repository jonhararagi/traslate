from __future__ import annotations

import pytest

from noveltrad.reader_pages import (
    page_source_hash,
    preserve_source_page_boundary,
    split_reader_pages,
    split_text_to_count,
)


def test_reader_pages_are_deterministic_and_round_trip_without_losing_source():
    text = ("Paragraph one. " + "word " * 250 + "\r\n\r\n" +
            "第二段 — Oknodie reached lvl 10. " + "Steal skill " * 250)
    first = split_reader_pages(text, max_chars=420)
    second = split_reader_pages(text, max_chars=420)

    assert first == second
    assert len(first) > 2
    assert "".join(first) == text
    assert all(page for page in first)


def test_legacy_translation_partition_keeps_exact_text_and_requested_page_count():
    text = "First paragraph.\n\nSecond paragraph with ゲーム terms and emoji 🐈.\r\n\r\nFinal paragraph."
    for count in (1, 2, 3, 8, len(text) + 2):
        parts = split_text_to_count(text, count)
        assert len(parts) == count
        assert "".join(parts) == text


def test_empty_translation_yields_one_empty_slot_per_source_page():
    assert split_text_to_count("", 4) == ["", "", "", ""]


def test_page_source_hash_is_stable_and_sensitive_to_content():
    assert page_source_hash("Oknodie\n") == page_source_hash("Oknodie\n")
    assert page_source_hash("Oknodie") != page_source_hash("Oknodie\n")


@pytest.mark.parametrize("count", (0, -1, True, 1.5))
def test_translation_partition_rejects_invalid_page_count(count):
    with pytest.raises(ValueError):
        split_text_to_count("text", count)


def test_reader_split_rejects_invalid_page_size():
    with pytest.raises(ValueError):
        split_reader_pages("text", max_chars=0)



@pytest.mark.parametrize(
    ("original", "translated", "expected"),
    (
        ("word ", "palabra", "palabra "),
        ("paragraph.\\n\\n", "párrafo.", "párrafo.\\n\\n"),
        ("line\\r\\n", "línea", "línea\\r\\n"),
        ("last sentence.", "última oración.", "última oración."),
    ),
)
def test_translation_page_restores_exact_original_boundary(original, translated, expected):
    assert preserve_source_page_boundary(original, translated) == expected


def test_translation_page_boundary_does_not_duplicate_whitespace():
    assert preserve_source_page_boundary("word  ", "palabra  ") == "palabra  "
