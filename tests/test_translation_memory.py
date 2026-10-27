import json

import pytest

from noveltrad.translation_memory import (
    TranslationMemoryPackError,
    choose_complete_memory_match,
    normalize_memory_text,
    parse_translation_memory_pack,
)


def _record(page, source, target, *, count=2, terminal=True, status="draft"):
    return {
        "id": f"SYNTH-C003-P{page:02d}",
        "chapter_id": "SYNTH-C003",
        "page_index": page,
        "chapter_page_count": count,
        "chapter_ends_with_page_separator": terminal,
        "source_text": source,
        "target_text": target,
        "status": status,
    }


def _pack(*records):
    return ("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n").encode("utf-8")


def test_normalization_only_ignores_case_whitespace_and_bom():
    assert normalize_memory_text("\ufeffLine one.\nLINE   two. ") == "line one. line two."


def test_parser_preserves_text_but_downgrades_claimed_confirmation():
    original = _record(1, "Source  A.", "Texto A.", status="confirmed")
    second = _record(2, "Source B.", "Texto B.", status="confirmed")
    parsed = parse_translation_memory_pack(_pack(original, second))
    assert len(parsed) == 2
    assert parsed[0]["target_text"] == "Texto A."
    assert parsed[0]["status"] == "draft"
    assert parsed[0]["chapter_page_count"] == 2
    assert parsed[0]["chapter_ends_with_page_separator"] is True


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ((_record(1, "A", "B"),), "incompleto"),
        ((_record(1, "A", "B"), _record(2, "C", "D", count=3)), "incoherentes"),
        ((_record(1, "A", "B"), _record(2, "C", "D", terminal=False)), "incoherentes"),
    ],
)
def test_parser_rejects_incomplete_or_inconsistent_chapter_metadata(records, message):
    with pytest.raises(TranslationMemoryPackError, match=message):
        parse_translation_memory_pack(_pack(*records))


def test_match_requires_full_chapter_and_preserves_final_form_feed():
    pack = parse_translation_memory_pack(_pack(
        _record(1, "First page.", "Primera página."),
        _record(2, "Second page.", "Segunda página."),
    ))
    entries = [dict(item, status="confirmed") for item in pack]
    match = choose_complete_memory_match(
        "First page.\fSecond page.\f", entries, memory_chapter_ref="SYNTH-C003"
    )
    assert match is not None
    assert match["proposed_text"] == "Primera página.\fSegunda página.\f"
    assert match["status"] == "confirmed"
    partial = choose_complete_memory_match(
        "First page.\f", entries, memory_chapter_ref="SYNTH-C003"
    )
    assert partial is None


def test_match_with_any_unconfirmed_page_is_draft_and_rejected_pages_are_excluded():
    pack = parse_translation_memory_pack(_pack(
        _record(1, "First page.", "Primera página."),
        _record(2, "Second page.", "Segunda página."),
    ))
    mixed = [dict(pack[0], status="confirmed"), dict(pack[1], status="draft")]
    match = choose_complete_memory_match("First page.\fSecond page.\f", mixed, include_draft=True)
    assert match is not None
    assert match["status"] == "draft"
    rejected = [dict(item, status="rejected") for item in pack]
    assert choose_complete_memory_match("First page.\fSecond page.\f", rejected, include_draft=True) is None


def test_retrieval_uses_confirmed_relevant_examples_only_and_excludes_exact_pages():
    from noveltrad.translation_memory import retrieve_confirmed_translation_examples

    query = "Oknodie uses the cursed artifact during magic training."
    entries = [
        {
            "chapter_ref": "V02-C010", "page_index": 2,
            "source_text": "During magic training, Oknodie uses Steal on a cursed artifact.",
            "target_text": "Durante el entrenamiento mágico, Oknodie usa Robar sobre un artefacto maldito.",
            "status": "confirmed",
        },
        {
            "chapter_ref": "V02-C011", "page_index": 1,
            "source_text": "During magic training, Oknodie uses Steal on a cursed artifact.",
            "target_text": "Borrador potencialmente incorrecto que aún no fue aprobado.",
            "status": "draft",
        },
        {
            "chapter_ref": "V02-C012", "page_index": 4,
            "source_text": "During magic training, Oknodie uses Steal on a cursed artifact.",
            "target_text": "Entrada rechazada.",
            "status": "rejected",
        },
        {
            "chapter_ref": "V03-C001", "page_index": 1,
            "source_text": "A sailor repaired the ship near the harbor.",
            "target_text": "Un marinero reparó el barco cerca del puerto.",
            "status": "confirmed",
        },
        {
            "chapter_ref": "V02-C009", "page_index": 3,
            "source_text": query,
            "target_text": "Esta página coincidiría exactamente y no debe entrar como ejemplo.",
            "status": "confirmed",
        },
    ]

    selected = retrieve_confirmed_translation_examples(query, entries)
    assert len(selected) == 1
    assert selected[0]["chapter_ref"] == "V02-C010"
    assert selected[0]["target_text"].startswith("Durante el entrenamiento")
    assert {"oknodie", "magic", "training"} <= set(selected[0]["matched_terms"])


def test_retrieval_respects_example_and_total_context_budgets():
    from noveltrad.translation_memory import retrieve_confirmed_translation_examples

    entries = [
        {
            "chapter_ref": f"V02-C{i:03d}",
            "page_index": 1,
            "source_text": "Oknodie magic training cursed artifact.",
            "target_text": "Oknodie: artefacto maldito durante el entrenamiento mágico.",
            "status": "confirmed",
        }
        for i in range(3)
    ]
    selected = retrieve_confirmed_translation_examples(
        "Oknodie magic training cursed artifact",
        entries,
        max_examples=3,
        max_context_chars=450,
        max_example_chars=100,
    )
    assert len(selected) == 2
    assert all(item["pair_chars"] <= 100 for item in selected)
    assert sum(item["pair_chars"] + 120 for item in selected) <= 450


def test_prompt_retrieval_reads_only_confirmed_local_memory(tmp_path):
    import sqlite3

    from noveltrad.translation_memory_api import get_translation_memory_examples_for_prompt

    database = tmp_path / "translation_memory.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE translation_memory_entries (
                book_id TEXT,
                chapter_ref TEXT,
                page_index INTEGER,
                source_text TEXT,
                target_text TEXT,
                status TEXT,
                imported_at TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO translation_memory_entries
            (book_id, chapter_ref, page_index, source_text, target_text, status, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "book-a", "V02-C010", 1,
                    "Oknodie uses Steal during magic training.",
                    "Oknodie usa Robar durante el entrenamiento mágico.",
                    "confirmed", "2026-10-27T10:00:00+00:00",
                ),
                (
                    "book-a", "V02-C011", 1,
                    "Oknodie uses Steal during magic training.",
                    "Borrador sin aprobar.",
                    "draft", "2026-10-26T10:00:00+00:00",
                ),
                (
                    "book-b", "V02-C012", 1,
                    "Oknodie uses Steal during magic training.",
                    "Otro libro.",
                    "confirmed", "2026-10-27T10:00:00+00:00",
                ),
            ],
        )

    examples = get_translation_memory_examples_for_prompt(
        lambda: tmp_path,
        "book-a",
        "Oknodie uses the Steal ability during magic training.",
    )
    assert len(examples) == 1
    assert examples[0]["chapter_ref"] == "V02-C010"
    assert examples[0]["target_text"] == "Oknodie usa Robar durante el entrenamiento mágico."

    assert get_translation_memory_examples_for_prompt(
        lambda: tmp_path / "not-created", "book-a", "Oknodie uses Steal magic training"
    ) == []
