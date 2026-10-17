from __future__ import annotations

import json

import pytest

from noveltrad.learning_store import LEARNING_FILES, TranslationLearningStore


def test_learning_decisions_are_separate_and_deduplicated(tmp_path):
    store = TranslationLearningStore(tmp_path)
    first = store.record_decision(
        category="terminology", source="farm", target="farmear",
        decision_type="contextual-gamer-verb", context="farm for XP",
        chapter=1, evidence="She farmed XP all night.", status="candidate",
    )
    duplicate = store.record_decision(
        category="terminology", source=" FARM ", target="FARMEAR",
        decision_type="contextual-gamer-verb", context="farm for XP",
        chapter=1, evidence="She farmed XP all night.", status="candidate",
    )
    enriched = store.record_decision(
        category="terminology", source="farm", target="farmear",
        decision_type="contextual-gamer-verb", context="farm materials",
        chapter=2, evidence="They farm materials before the raid.", status="confirmed",
    )

    assert first["created"] is True
    assert duplicate["created"] is False
    assert enriched["created"] is False
    payload = json.loads((tmp_path / "aprendizaje" / LEARNING_FILES["terminology"]).read_text())
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["status"] == "confirmed"
    assert len(payload["entries"][0]["evidence"]) == 2
    assert not (tmp_path / "traduccion").exists()


def test_repeated_evidence_does_not_duplicate_and_rejected_rule_is_not_promoted(tmp_path):
    store = TranslationLearningStore(tmp_path)
    store.record_decision(
        category="ambiguities", source="Steal", target="Steal",
        decision_type="protected-skill-name", context="Skill label",
        chapter=3, evidence="The Steal skill activated.", status="rejected",
    )
    result = store.record_decision(
        category="ambiguities", source="Steal", target="Steal",
        decision_type="protected-skill-name", context="Skill label",
        chapter=3, evidence="The Steal skill activated.", status="confirmed",
    )
    assert result["status"] == "rejected"
    payload = json.loads((tmp_path / "aprendizaje" / LEARNING_FILES["ambiguities"]).read_text())
    assert len(payload["entries"]) == 1
    assert len(payload["entries"][0]["evidence"]) == 1


def test_chapter_markdown_export_is_separate_and_safe(tmp_path):
    store = TranslationLearningStore(tmp_path)
    chapter = store.save_chapter(1, "../../ Oknodie: Start!", "La protagonista entra en la academia.")
    assert chapter.parent == (tmp_path / "traduccion")
    assert chapter.name == "capitulo-001-oknodie-start.md"
    assert chapter.read_text(encoding="utf-8") == (
        "# Capítulo 001 — ../../ Oknodie: Start!\n\n"
        "La protagonista entra en la academia.\n"
    )
    assert not (tmp_path / "aprendizaje" / chapter.name).exists()


@pytest.mark.parametrize("chapter", [0, -1, True, 1.5])
def test_invalid_chapter_number_is_rejected(tmp_path, chapter):
    store = TranslationLearningStore(tmp_path)
    with pytest.raises(ValueError):
        store.save_chapter(chapter, "Title", "Translated prose")


def test_empty_translation_and_invalid_category_are_rejected(tmp_path):
    store = TranslationLearningStore(tmp_path)
    with pytest.raises(ValueError):
        store.save_chapter(1, "Title", "  ")
    with pytest.raises(ValueError):
        store.record_decision(
            category="actions", source="attacked", target="atacó",
            decision_type="narrative-action", context="fight", chapter=1,
            evidence="She attacked.", status="candidate",
        )


def test_learning_index_reports_confirmed_and_candidate_counts(tmp_path):
    store = TranslationLearningStore(tmp_path)
    store.record_decision(
        category="names", source="Oknodie", target="Oknodie",
        decision_type="proper-name", context="character name", chapter=1,
        evidence="Oknodie arrived.", status="confirmed",
    )
    path = store.export_learning_index()
    assert path.parent == tmp_path / "aprendizaje"
    text = path.read_text(encoding="utf-8")
    assert "nombres-y-personajes.json" in text
    assert "1 confirmadas" in text
    assert "../traduccion/" in text
