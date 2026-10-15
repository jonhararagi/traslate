from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from noveltrad import main


def _create_book(source: str) -> tuple[str, str]:
    book_id = str(uuid4())
    chapter_id = str(uuid4())
    now = "2026-10-15T00:00:00+00:00"
    with main.connection() as conn:
        conn.execute(
            "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) VALUES(?,?,?,?,?,?)",
            (book_id, "Quality warning test", "epub", "quality-test.epub", "unused", now),
        )
        conn.execute(
            "INSERT INTO chapters(id,book_id,chapter_index,title,original_text,translated_text,status) "
            "VALUES(?,?,?,?,?,?,?)",
            (chapter_id, book_id, 0, "Chapter 1", source, "", "imported"),
        )
    return book_id, chapter_id


def test_quality_diagnostics_flag_identical_too_short_and_model_placeholders():
    original = (
        "The protagonist carefully checks the inventory, compares every item, "
        "records the result in her journal, and then returns to the academy."
    ) * 3

    identical = main._translation_quality_warnings(original, original)
    assert any("coincide con el original" in warning for warning in identical)

    too_short = main._translation_quality_warnings(original, "Done.")
    assert any("mucho más corta" in warning for warning in too_short)

    placeholder = main._translation_quality_warnings(
        original,
        "La traducción omitida [translation omitted]",
    )
    assert any("marca de omisión" in warning for warning in placeholder)


def test_quality_diagnostics_detect_repeated_output_not_repeated_in_source():
    original = (
        "The protagonist opens the inventory, counts each potion, and closes it. "
        "She then returns to the academy and prepares for the next lesson."
    ) * 2
    repeated_sentence = "The generated translation repeats this complete sentence without adding new information."
    translated = repeated_sentence + " " + repeated_sentence

    warnings = main._translation_quality_warnings(original, translated)
    assert any("oración larga repetida" in warning for warning in warnings)


def test_quality_diagnostics_do_not_flag_a_reasonable_short_translation():
    original = (
        "The heroine entered the academy library, checked the inventory, and carefully recorded "
        "the items she would need for the next quest."
    )
    translated = (
        "La protagonista entró en la biblioteca de la academia, revisó el inventario "
        "y anotó con cuidado los objetos que necesitaría para la próxima misión."
    )

    assert main._translation_quality_warnings(original, translated) == []


def test_quality_warnings_are_persisted_and_returned_for_queue_chunks(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-data"))
    main.init_db()
    source = (
        "The protagonist carefully checks the inventory, compares every item, "
        "records the result in her journal, and then returns to the academy. "
    ) * 4
    book_id, _ = _create_book(source)

    def poor_translation(text, glossary, continuity_context=""):
        return "Done."

    monkeypatch.setattr(main, "_translate_with_local_model", poor_translation)
    with TestClient(main.app) as client:
        created = client.post(f"/api/books/{book_id}/translation-jobs", json={})
        assert created.status_code == 200, created.text
        job_id = created.json()["id"]

        processed = client.post(f"/api/translation-jobs/{job_id}/run-next")
        assert processed.status_code == 200, processed.text
        state = processed.json()
        assert state["status"] == "completed"
        assert state["quality_warning_chunks"] == 1
        assert state["chunks"][0]["quality_warning_count"] >= 1
        assert any("mucho más corta" in warning for warning in state["chunks"][0]["quality_warnings"])

        chunk_id = state["chunks"][0]["id"]
        detail = client.get(f"/api/translation-jobs/{job_id}/chunks/{chunk_id}")
        assert detail.status_code == 200
        assert detail.json()["quality_warnings"] == state["chunks"][0]["quality_warnings"]

        reviewed = client.put(
            f"/api/translation-jobs/{job_id}/chunks/{chunk_id}",
            json={"translated_text": "La protagonista revisa cuidadosamente el inventario, compara cada objeto, anota el resultado en su diario y después regresa a la academia. " * 4},
        )
        assert reviewed.status_code == 200, reviewed.text
        refreshed = client.get(f"/api/translation-jobs/{job_id}").json()
        assert refreshed["reviewed_chunks"] == 1
        assert refreshed["quality_warning_chunks"] == 0
        assert refreshed["chunks"][0]["quality_warnings"] == []
