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
    match = choose_complete_memory_match("First page.\fSecond page.\f", mixed)
    assert match is not None
    assert match["status"] == "draft"
    rejected = [dict(item, status="rejected") for item in pack]
    assert choose_complete_memory_match("First page.\fSecond page.\f", rejected, include_draft=True) is None
